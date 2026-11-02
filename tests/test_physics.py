import math
import unittest
from rules import Game, Bat


class CollisionTests(unittest.TestCase):
    def test_overlap_and_large_enemy_mass(self):
        g = Game()
        radius = g.config['enemies']['bat']['radius']
        a = Bat(0, 0, 8)
        b = Bat(radius, 0, 8)
        g.bats = [a, b]
        g.separate_enemies()
        self.assertGreater(b.x - a.x, radius)
        self.assertAlmostEqual(a.x + b.x, radius)
        boss = Bat(0, 0, g.config['enemies']['demon']['hp'], kind='demon')
        small = Bat(radius, 0, 8)
        g.bats = [boss, small]
        g.separate_enemies()
        self.assertGreater(small.x - radius, abs(boss.x))

    def test_coincident_disabled_and_distant(self):
        g = Game()
        a, b = Bat(0, 0, 8), Bat(0, 0, 8)
        g.bats = [a, b]
        g.separate_enemies()
        self.assertTrue(math.isfinite(a.x))
        self.assertGreater(b.x - a.x, 0)
        before = (a.x, b.x)
        g.config['physics']['enabled'] = False
        g.separate_enemies()
        self.assertEqual((a.x, b.x), before)
        g.config['physics']['enabled'] = True
        a.x, b.x = 0, g.config['spawn']['radius']
        g.separate_enemies()
        self.assertEqual((a.x, b.x), (0, g.config['spawn']['radius']))

    def test_hit_recoil_damping_and_boss_mass(self):
        g = Game()
        a = Bat(100, 0, 1000)
        boss = Bat(100, 100, 1000, kind='demon')
        g.bats = [a, boss]
        g.damage_enemy(a, 1)
        g.damage_enemy(boss, 1)
        speed = math.hypot(a.push_x, a.push_y)
        self.assertGreater(speed, math.hypot(boss.push_x, boss.push_y))
        g.shot_wait = 1000
        g.update()
        self.assertGreater(a.x, 100)
        self.assertLess(math.hypot(a.push_x, a.push_y), speed)
        for _ in range(10):
            g.damage_enemy(a, 1)
        self.assertLessEqual(math.hypot(a.push_x, a.push_y), g.config['physics']['max_push_speed'])
        g.config['physics']['enabled'] = False
        before = a.push_x
        g.damage_enemy(a, 1)
        self.assertEqual(a.push_x, before)

    def test_collision_transfers_momentum_without_adding_energy(self):
        g = Game()
        radius = g.config['enemies']['bat']['radius']
        first, second = Bat(0, 0, 100), Bat(radius, 0, 100)
        first.push_x = g.config['physics']['hit_impulse']
        initial_momentum = first.push_x
        initial_energy = first.push_x ** 2
        g.bats = [first, second]
        g.separate_enemies()
        self.assertGreater(second.push_x, 0)
        self.assertAlmostEqual(first.push_x + second.push_x, initial_momentum)
        self.assertLessEqual(first.push_x ** 2 + second.push_x ** 2, initial_energy)

    def test_hero_recoil_freezes_when_paused(self):
        g = Game()
        g.shot_wait = 1000
        g.bats = [Bat(-1, 0, 100)]
        g.update()
        self.assertGreater(g.push_x, 0)
        g.bats = []
        x = g.x
        g.paused = True
        g.update()
        self.assertEqual(g.x, x)
        g.paused = False
        g.update()
        self.assertGreater(g.x, x)
        self.assertLess(g.push_x, g.config['physics']['hero_impulse'])
