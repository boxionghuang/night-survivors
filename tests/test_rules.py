import math
import random
import unittest

from rules import Bat, Game, load_config


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.cfg = load_config()
        self.game = Game(self.cfg, random.Random(7))

    def advance(self, seconds, direction=(0, 0)):
        for _ in range(round(seconds / self.cfg["step_seconds"])):
            self.game.update(direction)

    def test_spawn_circle_minimum_and_cap(self):
        spawn = self.cfg["spawn"]
        self.game.spawn_bats()
        self.assertEqual(len(self.game.bats), spawn["per_tick"])
        for bat in self.game.bats:
            self.assertAlmostEqual(math.hypot(bat.x, bat.y), spawn["radius"])
        self.game.spawn_bats()
        self.assertEqual(len(self.game.bats), self.cfg["waves"][0]["minimum"])
        for wave in self.cfg["waves"]:
            self.game.bats = []
            self.game.elapsed = wave["from"]
            for _ in range(spawn["max_alive"]):
                self.game.spawn_bats()
            self.assertEqual(len(self.game.bats), min(wave["minimum"], spawn["max_alive"]))

    def test_spawn_clock_and_removal(self):
        self.advance(self.cfg["spawn"]["interval"] - self.cfg["step_seconds"])
        self.assertEqual(len(self.game.bats), 0)
        self.game.update()
        self.assertEqual(len(self.game.bats), self.cfg["spawn"]["per_tick"])
        self.game.bats = [Bat(self.cfg["spawn"]["remove_radius"] + 1, 0, 8)]
        self.game.update()
        self.assertEqual(self.game.bats, [])

    def test_contact_cooldown_and_game_over(self):
        bat = self.cfg["enemies"]["bat"]
        self.game.bats = [Bat(0, 0, bat["hp"])]
        self.game.shot_wait = 1000  # Isolate contact from the automatic weapon.
        self.game.spawn_wait = 1000
        self.game.update()
        self.assertEqual(self.game.hp, self.cfg["hero"]["hp"] - bat["damage"])
        self.advance(self.cfg["contact_interval"] - self.cfg["step_seconds"])
        self.assertEqual(self.game.hp, self.cfg["hero"]["hp"] - bat["damage"])
        self.game.update()
        self.assertEqual(self.game.hp, self.cfg["hero"]["hp"] - 2 * bat["damage"])
        self.advance(self.cfg["contact_interval"] * math.ceil(self.cfg["hero"]["hp"] / bat["damage"]))
        self.assertTrue(self.game.game_over)
        self.assertEqual(self.game.hp, 0)
        elapsed = self.game.elapsed
        self.game.update((100, 0))
        self.assertEqual(self.game.elapsed, elapsed)
        self.assertEqual(Game(self.cfg).hp, self.cfg["hero"]["hp"])

    def test_wand_targets_nearest_and_kills(self):
        hp = self.cfg["enemies"]["bat"]["hp"]
        far = Bat(-200, 0, hp)
        near = Bat(60, 0, hp)
        self.game.bats = [far, near]
        self.game.update()
        self.assertGreater(self.game.sparks[0].vx, 0)
        self.advance(0.2)
        self.assertNotIn(near, self.game.bats)
        self.assertIn(far, self.game.bats)
        self.assertEqual(self.game.kills, 1)

    def test_movement_dead_zone_and_pause(self):
        self.advance(1, (100, 0))
        self.assertAlmostEqual(self.game.x, self.cfg["hero"]["speed"])
        position = self.game.x
        self.game.update((self.cfg["screen"]["dead_zone"], 0))
        self.assertEqual(self.game.x, position)
        self.game.paused = True
        elapsed = self.game.elapsed
        self.game.update((100, 100))
        self.assertEqual(self.game.x, position)
        self.assertEqual(self.game.elapsed, elapsed)


if __name__ == "__main__":
    unittest.main()
