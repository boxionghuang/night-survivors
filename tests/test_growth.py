import unittest
from rules import Game, Bat, Gem


class GrowthTests(unittest.TestCase):
    def setUp(self):
        self.g = Game()
        self.c = self.g.config
        self.g.spawn_wait = 1000
        self.g.shot_wait = 1000

    def test_gems_level_pause_and_overflow(self):
        g = self.g
        need = g.xp_needed
        g.gems = [Gem(g.x, g.y, need + 2)]
        g.update()
        self.assertEqual(g.level, 2)
        self.assertEqual(g.xp, 2)
        self.assertEqual(len(g.cards), self.c['growth']['cards'])
        elapsed = g.elapsed
        g.update((100, 0))
        self.assertEqual(g.elapsed, elapsed)
        g.choose_card(0)
        self.assertFalse(g.cards)
        self.assertEqual(g.xp_needed, need + self.c['growth']['xp_increment'])

    def test_passives_caps_and_heal(self):
        g = self.g
        for name in g.passives:
            g.cards = [name]
            g.choose_card(0)
        self.assertEqual(g.max_hp, self.c['hero']['hp'] + self.c['passives']['heart_hp'])
        self.assertEqual(g.hp, g.max_hp)
        self.assertEqual(g.speed, self.c['hero']['speed'] * (1 + self.c['passives']['boots_speed_bonus']))
        self.assertEqual(g.magnet_radius, self.c['hero']['magnet_radius'] + self.c['passives']['magnet_radius'])
        g.weapons = dict.fromkeys(('spark', 'blades', 'ring'), self.c['weapons']['max_level'])
        g.passives = dict.fromkeys(g.passives, self.c['passives']['max_level'])
        g.xp = g.xp_needed
        g.check_level_up()
        self.assertEqual(set(g.cards), {'heal'})
        g.hp = 1
        g.choose_card(0)
        self.assertEqual(g.hp, 1 + self.c['growth']['fallback_heal'])

    def test_ring_and_blade_cooldowns_and_drop(self):
        g = self.g
        g.weapons['ring'] = 1
        ring = g.weapon_stats('ring')
        bat = Bat(ring['radius'] / 2, 0, 1000)
        g.bats = [bat]
        g.update()
        self.assertEqual(bat.hp, 1000 - ring['damage'])
        g.update()
        self.assertEqual(bat.hp, 1000 - ring['damage'])
        del g.weapons['ring']
        g.weapons['blades'] = 1
        x, y = g.blade_positions()[0]
        bat.x, bat.y = x, y
        hp = bat.hp
        g.update()
        self.assertEqual(bat.hp, hp - g.weapon_stats('blades')['damage'])
        g.update()
        self.assertEqual(bat.hp, hp - g.weapon_stats('blades')['damage'])
        g.damage_enemy(bat, bat.hp)
        self.assertEqual(g.kills, 1)
        self.assertEqual(g.gems[0].xp, self.c['enemies']['bat']['xp'])

    def test_weapon_scaling(self):
        for name in ('spark', 'blades', 'ring'):
            level = self.c['weapons']['max_level']
            self.g.weapons[name] = level
            stats = self.g.weapon_stats(name)
            base = self.c['weapons'][name]
            self.assertEqual(stats['damage'], base['damage'] + (level - 1) * base['damage_per_level'])
        self.assertEqual(self.g.weapon_stats('spark')['count'], self.c['weapons']['spark']['count'] + len(self.c['weapons']['spark']['extra_spark_levels']))
