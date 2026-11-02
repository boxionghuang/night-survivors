import math
import random
import unittest
from rules import Game, Bat


class WaveTests(unittest.TestCase):
    def setUp(self):
        self.g = Game(rng=random.Random(4))
        self.c = self.g.config

    def test_wave_types_and_spawn_budget(self):
        for wave in self.c['waves']:
            g = Game(self.c, random.Random(4))
            g.elapsed = wave['from']
            g.spawn_bats()
            self.assertLessEqual(len(g.bats), self.c['spawn']['per_tick'])
            self.assertTrue(all(b.kind in wave['types'] or b.kind == 'demon' for b in g.bats))
            for b in g.bats:
                self.assertEqual(b.hp, self.c['enemies'][b.kind]['hp'])

    def test_boss_once_cap_and_return(self):
        g = self.g
        g.elapsed = next(w['from'] for w in self.c['waves'] if 'boss' in w)
        g.bats = [Bat(0, 0, 8) for _ in range(self.c['spawn']['max_alive'])]
        g.spawn_bats()
        self.assertEqual(len(g.bats), self.c['spawn']['max_alive'])
        boss = next(b for b in g.bats if b.kind == 'demon')
        g.bats = [boss, Bat(self.c['spawn']['remove_radius'] + 10, 0, 8)]
        boss.x = self.c['spawn']['boss_return_radius'] + 10
        boss.y = 0
        g.shot_wait = 1000
        g.update()
        self.assertEqual(len(g.bats), 1)
        expected = self.c['spawn']['radius'] - self.c['enemies']['demon']['speed'] * self.c['step_seconds']
        self.assertAlmostEqual(math.hypot(boss.x, boss.y), expected)
        g.damage_enemy(boss, boss.hp)
        g.spawn_bats()
        self.assertFalse(any(b.kind == 'demon' for b in g.bats))

    def test_enemy_speed_damage_and_xp(self):
        for kind, stats in self.c['enemies'].items():
            g = Game(self.c)
            g.shot_wait = 1000
            enemy = Bat(100, 0, stats['hp'], kind=kind)
            g.bats = [enemy]
            g.update()
            self.assertAlmostEqual(enemy.x, 100 - stats['speed'] * self.c['step_seconds'])
            enemy.x = enemy.y = 0
            g.update()
            self.assertEqual(g.hp, self.c['hero']['hp'] - stats['damage'])
            g.damage_enemy(enemy, enemy.hp)
            self.assertEqual(g.gems[-1].xp, stats['xp'])

    def test_victory_pause_and_restart(self):
        g = self.g
        g.elapsed = self.c['victory_seconds'] - self.c['step_seconds']
        g.paused = True
        g.update()
        self.assertFalse(g.victory)
        g.paused = False
        g.update()
        self.assertTrue(g.victory)
        self.assertFalse(g.game_over)
        self.assertEqual(g.elapsed, self.c['victory_seconds'])
        g.update((100, 0))
        self.assertEqual(g.x, 0)
        fresh = Game(self.c)
        self.assertFalse(fresh.ended)
        self.assertFalse(fresh.boss_spawned)
