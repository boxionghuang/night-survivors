"""Core simulation. All positions are world positions; one update is 1/60 s."""
from dataclasses import dataclass, field
import json
import math
from pathlib import Path
import random


def load_config():
    with (Path(__file__).parent / "data" / "game.json").open() as source:
        return json.load(source)


@dataclass
class Bat:
    x: float
    y: float
    hp: float
    hit_wait: float = 0
    blade_hits: dict = field(default_factory=dict)
    kind: str = "bat"
    push_x: float = 0
    push_y: float = 0


@dataclass
class Spark:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    damage: float = 0


@dataclass
class Gem:
    x: float
    y: float
    xp: int
    attracted: bool = False


class Game:
    def __init__(self, config=None, rng=None):
        self.config = config if config is not None else load_config()
        self.rng = rng if rng is not None else random.Random()
        self.x = self.y = self.elapsed = 0.0
        self.push_x = self.push_y = 0.0
        self.hp = self.config["hero"]["hp"]
        self.bats = []
        self.sparks = []
        self.kills = 0
        self.events = []
        self.game_over = False
        self.victory = False
        self.boss_spawned = False
        self.paused = False
        self.spawn_wait = self.config["spawn"]["interval"]
        self.shot_wait = 0.0
        self.weapons = {"spark": 1}
        self.passives = {"boots": 0, "heart": 0, "magnet": 0}
        self.level = 1
        self.xp = 0
        self.gems = []
        self.cards = []
        self.ring_wait = 0.0

    @property
    def max_hp(self):
        return self.config["hero"]["hp"] + self.passives["heart"] * self.config["passives"]["heart_hp"]

    @property
    def speed(self):
        return self.config["hero"]["speed"] * (1 + self.passives["boots"] * self.config["passives"]["boots_speed_bonus"])

    @property
    def magnet_radius(self):
        return self.config["hero"]["magnet_radius"] + self.passives["magnet"] * self.config["passives"]["magnet_radius"]

    @property
    def xp_needed(self):
        return self.config["growth"]["initial_xp"] + (self.level - 1) * self.config["growth"]["xp_increment"]

    def weapon_stats(self, name):
        stats = dict(self.config["weapons"][name])
        level = self.weapons.get(name, 1)
        stats["damage"] += (level - 1) * stats["damage_per_level"]
        if name == "spark":
            stats["interval"] -= (level - 1) * stats["interval_reduction"]
            stats["count"] += sum(level >= n for n in stats["extra_spark_levels"])
        elif name == "blades":
            stats["count"] += sum(level >= n for n in stats["extra_blade_levels"])
        else:
            stats["radius"] += (level - 1) * stats["radius_per_level"]
        return stats

    def blade_positions(self):
        if "blades" not in self.weapons:
            return []
        stats = self.weapon_stats("blades")
        return [(self.x + math.cos(self.elapsed * math.tau / stats["period"] + i * math.tau / stats["count"]) * stats["radius"],
                 self.y + math.sin(self.elapsed * math.tau / stats["period"] + i * math.tau / stats["count"]) * stats["radius"])
                for i in range(stats["count"])]

    def damage_enemy(self, bat, damage):
        physics = self.config["physics"]
        if physics["enabled"]:
            dx, dy = bat.x - self.x, bat.y - self.y
            distance = math.hypot(dx, dy)
            nx, ny = (dx / distance, dy / distance) if distance else (1, 0)
            radius = self.config["enemies"][bat.kind]["radius"]
            mass_ratio = (self.config["enemies"]["bat"]["radius"] / radius) ** 2
            impulse = physics["hit_impulse"] * mass_ratio
            bat.push_x += nx * impulse
            bat.push_y += ny * impulse
            speed = math.hypot(bat.push_x, bat.push_y)
            if speed > physics["max_push_speed"]:
                scale = physics["max_push_speed"] / speed
                bat.push_x *= scale
                bat.push_y *= scale
        self.events.append(("hit", bat.x, bat.y, damage))
        bat.hp -= damage
        if bat.hp <= 0:
            self.bats.remove(bat)
            self.kills += 1
            self.events.append(("death", bat.x, bat.y, 0))
            self.gems.append(Gem(bat.x, bat.y, self.config["enemies"][bat.kind]["xp"]))

    def check_level_up(self):
        if self.cards or self.xp < self.xp_needed:
            return
        self.xp -= self.xp_needed
        self.level += 1
        self.events.append(("level_up", self.x, self.y, 0))
        options = [name for name in ("spark", "blades", "ring")
                   if self.weapons.get(name, 0) < self.config["weapons"]["max_level"]
                   and (name in self.weapons or len(self.weapons) < self.config["weapons"]["max_owned"])]
        options += [name for name, level in self.passives.items()
                    if level < self.config["passives"]["max_level"]]
        count = self.config["growth"]["cards"]
        self.cards = self.rng.sample(options, min(count, len(options))) if options else ["heal"]
        # Repeat legal choices when fewer than three upgrades remain.
        while len(self.cards) < count:
            self.cards.append(self.rng.choice(self.cards))

    def choose_card(self, index):
        if not self.cards or not 0 <= index < len(self.cards):
            return
        name = self.cards[index]
        self.events.append(("upgrade", self.x, self.y, 0))
        if name == "heal":
            self.hp = min(self.max_hp, self.hp + self.config["growth"]["fallback_heal"])
        elif name in self.passives:
            self.passives[name] += 1
            if name == "heart":
                self.hp = min(self.max_hp, self.hp + self.config["passives"]["heart_heal"])
        else:
            self.weapons[name] = self.weapons.get(name, 0) + 1
        self.cards = []
        self.check_level_up()

    def collect_gems(self, dt):
        for gem in self.gems[:]:
            dx, dy = self.x - gem.x, self.y - gem.y
            distance = math.hypot(dx, dy)
            gem.attracted = gem.attracted or distance <= self.magnet_radius
            if gem.attracted:
                travel = self.config["growth"]["gem_speed"] * dt
                if distance <= travel + self.config["hero"]["radius"]:
                    self.events.append(("gem", gem.x, gem.y, gem.xp))
                    self.xp += gem.xp
                    self.gems.remove(gem)
                else:
                    gem.x += dx / distance * travel
                    gem.y += dy / distance * travel
        self.check_level_up()


    @property
    def ended(self):
        return self.game_over or self.victory

    def place_on_spawn_circle(self, enemy):
        angle = self.rng.uniform(0, math.tau)
        radius = self.config["spawn"]["radius"]
        enemy.x = self.x + math.cos(angle) * radius
        enemy.y = self.y + math.sin(angle) * radius

    def spawn_enemy(self, kind):
        enemy = Bat(0, 0, self.config["enemies"][kind]["hp"], kind=kind)
        self.place_on_spawn_circle(enemy)
        self.bats.append(enemy)

    def spawn_bats(self):
        """Fill the current wave; retain the original method name for callers."""
        settings = self.config["spawn"]
        wave = max((w for w in self.config["waves"] if w["from"] <= self.elapsed + 1e-9),
                   key=lambda w: w["from"])
        budget = settings["per_tick"]
        boss_wave = next(w for w in self.config["waves"] if "boss" in w)
        if not self.boss_spawned and self.elapsed + 1e-9 >= boss_wave["from"]:
            # Reserve a slot for the one-time boss even at the hard cap.
            if len(self.bats) >= settings["max_alive"]:
                self.bats.pop(0)
            self.spawn_enemy(boss_wave["boss"])
            self.boss_spawned = True
            budget -= 1
        count = max(0, min(budget, wave["minimum"] - len(self.bats),
                           settings["max_alive"] - len(self.bats)))
        for _ in range(count):
            self.spawn_enemy(self.rng.choice(wave["types"]))

    def separate_enemies(self):
        """Resolve circle overlaps; area acts as mass, so big enemies move less."""
        settings = self.config["physics"]
        if not settings["enabled"]:
            return
        for _ in range(settings["iterations"]):
            for i, first in enumerate(self.bats):
                first_radius = self.config["enemies"][first.kind]["radius"]
                for second in self.bats[i + 1:]:
                    second_radius = self.config["enemies"][second.kind]["radius"]
                    dx, dy = second.x - first.x, second.y - first.y
                    distance_sq = dx * dx + dy * dy
                    minimum = first_radius + second_radius
                    if distance_sq >= minimum * minimum:
                        continue
                    distance = math.sqrt(distance_sq)
                    # A fixed direction also separates exactly coincident centres.
                    nx, ny = (dx / distance, dy / distance) if distance else (1, 0)
                    correction = max(0, minimum - distance - settings["slop"]) * settings["strength"]
                    first_share = second_radius ** 2 / (first_radius ** 2 + second_radius ** 2)
                    first.x -= nx * correction * first_share
                    first.y -= ny * correction * first_share
                    second.x += nx * correction * (1 - first_share)
                    second.y += ny * correction * (1 - first_share)
                    # Exchange only closing momentum, never add energy to separating bodies.
                    relative = ((second.push_x - first.push_x) * nx
                                + (second.push_y - first.push_y) * ny)
                    if relative < 0:
                        if -relative >= settings["bounce_sound_threshold"]:
                            self.events.append(("bounce", first.x, first.y, 0))
                        impulse = -(1 + settings["restitution"]) * relative
                        first.push_x -= nx * impulse * first_share
                        first.push_y -= ny * impulse * first_share
                        second.push_x += nx * impulse * (1 - first_share)
                        second.push_y += ny * impulse * (1 - first_share)

    def update(self, direction=(0, 0)):
        if self.ended or self.paused or self.cards:
            return
        cfg = self.config
        dt = cfg["step_seconds"]
        self.elapsed += dt
        if self.elapsed + 1e-9 >= cfg["victory_seconds"]:
            self.elapsed = cfg["victory_seconds"]
            self.victory = True
            self.events.append(("end", self.x, self.y, 0))
            return
        dx, dy = direction
        distance = math.hypot(dx, dy)
        if distance > cfg["screen"]["dead_zone"]:
            travel = min(self.speed * dt,
                         distance - cfg["screen"]["dead_zone"])
            self.x += dx / distance * travel
            self.y += dy / distance * travel

        if cfg["physics"]["enabled"]:
            self.x += self.push_x * dt
            self.y += self.push_y * dt
            damping = math.exp(-cfg["physics"]["drag"] * dt)
            self.push_x *= damping
            self.push_y *= damping

        self.bats = [b for b in self.bats if
                     b.kind == "demon" or math.hypot(b.x - self.x, b.y - self.y) <= cfg["spawn"]["remove_radius"]]
        for enemy in self.bats:
            if enemy.kind == "demon" and math.hypot(enemy.x - self.x, enemy.y - self.y) > cfg["spawn"]["boss_return_radius"]:
                self.place_on_spawn_circle(enemy)
        self.spawn_wait -= dt
        if self.spawn_wait <= 1e-9:
            self.spawn_bats()
            self.spawn_wait += cfg["spawn"]["interval"]

        wand = self.weapon_stats("spark")
        self.shot_wait = max(0, self.shot_wait - dt)
        if self.bats and self.shot_wait <= 1e-9:
            target = min(self.bats, key=lambda b: math.hypot(b.x - self.x, b.y - self.y))
            dx, dy = target.x - self.x, target.y - self.y
            length = math.hypot(dx, dy)
            vx, vy = (dx / length, dy / length) if length else (1, 0)
            for _ in range(wand["count"]):
                self.sparks.append(Spark(self.x, self.y, vx * wand["speed"],
                                         vy * wand["speed"], wand["lifetime"], wand["damage"]))
            self.shot_wait = wand["interval"]

        for bat in self.bats:
            dx, dy = self.x - bat.x, self.y - bat.y
            distance = math.hypot(dx, dy)
            if distance:
                travel = min(distance, cfg["enemies"][bat.kind]["speed"] * dt)
                bat.x += dx / distance * travel
                bat.y += dy / distance * travel
            if cfg["physics"]["enabled"]:
                bat.x += bat.push_x * dt
                bat.y += bat.push_y * dt
                damping = math.exp(-cfg["physics"]["drag"] * dt)
                bat.push_x *= damping
                bat.push_y *= damping
            bat.hit_wait = max(0, bat.hit_wait - dt)

        self.separate_enemies()

        for spark in self.sparks[:]:
            old_x, old_y = spark.x, spark.y
            spark.x += spark.vx * dt
            spark.y += spark.vy * dt
            spark.life -= dt
            # Test the whole travelled segment, so fast sparks cannot skip a bat.
            sx, sy = spark.x - old_x, spark.y - old_y
            length_sq = sx * sx + sy * sy
            hits = []
            for bat in self.bats:
                t = max(0, min(1, ((bat.x - old_x) * sx + (bat.y - old_y) * sy)
                               / length_sq)) if length_sq else 0
                if math.hypot(bat.x - old_x - t * sx, bat.y - old_y - t * sy) <= cfg["enemies"][bat.kind]["radius"] + wand["radius"]:
                    hits.append((t, bat))
            if hits:
                bat = min(hits, key=lambda hit: hit[0])[1]
                self.damage_enemy(bat, spark.damage)
            if hits or spark.life <= 0:
                self.sparks.remove(spark)

        if "ring" in self.weapons:
            self.ring_wait -= dt
            if self.ring_wait <= 1e-9:
                ring = self.weapon_stats("ring")
                self.ring_wait += ring["interval"]
                for bat in self.bats[:]:
                    if math.hypot(bat.x - self.x, bat.y - self.y) <= ring["radius"]:
                        self.damage_enemy(bat, ring["damage"])
        for index, (x, y) in enumerate(self.blade_positions()):
            blade = self.weapon_stats("blades")
            for bat in self.bats[:]:
                if (math.hypot(bat.x - x, bat.y - y) <= cfg["enemies"][bat.kind]["radius"] + blade["hit_radius"]
                        and self.elapsed + 1e-9 >= bat.blade_hits.get(index, 0)):
                    bat.blade_hits[index] = self.elapsed + blade["hit_interval"]
                    self.damage_enemy(bat, blade["damage"])

        for bat in self.bats:
            if (math.hypot(bat.x - self.x, bat.y - self.y) <= cfg["enemies"][bat.kind]["radius"] + cfg["hero"]["radius"]
                    and bat.hit_wait <= 1e-9):
                damage = cfg["enemies"][bat.kind]["damage"]
                if cfg["physics"]["enabled"]:
                    dx, dy = self.x - bat.x, self.y - bat.y
                    distance = math.hypot(dx, dy)
                    nx, ny = (dx / distance, dy / distance) if distance else (1, 0)
                    # Replace rather than stack impulses, keeping crowded hits controllable.
                    self.push_x = nx * cfg["physics"]["hero_impulse"]
                    self.push_y = ny * cfg["physics"]["hero_impulse"]
                self.events.append(("hurt", self.x, self.y, damage))
                self.hp = max(0, self.hp - damage)
                bat.hit_wait = cfg["contact_interval"]
                if self.hp == 0:
                    self.game_over = True
                    self.events.append(("end", self.x, self.y, 0))
                    break

        if not self.game_over:
            self.collect_gems(dt)
