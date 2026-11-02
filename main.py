"""Run with .venv/bin/python main.py. Run make_assets.py first to rebuild the pictures."""
import asyncio
import math
import random
import sys
from pathlib import Path
import pygame

from rules import Game, load_config


async def main():
    pygame.init()
    config = load_config()
    width, height = config["screen"]["width"], config["screen"]["height"]
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption("Night Survivors")
    assets = Path(__file__).parent / "assets"
    pictures = {name: pygame.image.load(str(assets / f"{name}.png")).convert_alpha()
                for name in ("hero", "bat", "slime", "ghost", "demon", "floor", "sword", "gem_blue", "gem_pink")}
    demon = pictures["demon"]
    scale = config["enemies"]["demon"]["draw_scale"]
    pictures["demon"] = pygame.transform.scale(demon, (demon.get_width() * scale, demon.get_height() * scale))
    font = pygame.font.Font(None, 24)
    title_font = pygame.font.Font(None, 44)
    clock = pygame.time.Clock()
    game = Game(config)
    feel = config["feel"]
    sounds = {}
    if pygame.mixer.get_init():
        for name in list(config["sound"]["notes"]) + list(config["sound"]["speech"]):
            for extension in ("ogg", "wav"):
                path = Path(__file__).parent / "sounds" / f"{name}.{extension}"
                if path.exists():
                    try:
                        sounds[name] = pygame.mixer.Sound(str(path))
                        sounds[name].set_volume(config["sound"]["volumes"].get(name, config["sound"]["volume"]))
                        break
                    except pygame.error:
                        continue
    effects = []
    sound_wait = {}
    voice_wait = 0.0
    voice_channel = None
    if pygame.mixer.get_init():
        pygame.mixer.set_reserved(1)
        voice_channel = pygame.mixer.Channel(0)
    shake_left = 0.0
    effect_game = game
    visual_rng = random.Random()
    pointer = (width / 2, height / 2)
    touch_id = None
    touch_mode = False
    accumulator = 0.0
    running = True

    def label(text, position, colour=(230, 236, 245), big=False):
        screen.blit((title_font if big else font).render(text, True, colour), position)

    names = {"spark": "Spark Wand", "blades": "Spin Blades", "ring": "Holy Ring",
             "boots": "Swift Boots", "heart": "Big Heart", "magnet": "Magnet"}
    descriptions = {"spark": "Stronger, faster automatic sparks", "blades": "Blades circle and strike enemies",
                    "ring": "Damage nearby enemies repeatedly",
                    "boots": f"+{config['passives']['boots_speed_bonus']:.0%} walking speed",
                    "heart": f"+{config['passives']['heart_hp']} max HP; heal {config['passives']['heart_heal']}",
                    "magnet": f"+{config['passives']['magnet_radius']} px gem attraction"}
    card_rects = [pygame.Rect(20, 175 + i * 140, width - 40, 120)
                  for i in range(config["growth"]["cards"])]

    def pick_card(position):
        for index, rect in enumerate(card_rects):
            if rect.collidepoint(position):
                game.choose_card(index)
                break

    while running:
        # The browser schedules frames; do not block its event loop with SDL delay.
        frame_seconds = min(clock.tick(0 if sys.platform == "emscripten" else 60) / 1000, 0.25)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_p:
                if not game.cards:
                    game.paused = not game.paused
            elif event.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN):
                if not getattr(event, "touch", False) and touch_id is None:
                    touch_mode = False
                    pointer = event.pos
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and game.cards:
                        pick_card(event.pos)
                        pointer = (width / 2, height / 2)
                    elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and game.ended:
                        game = Game(config)
                        accumulator = 0
            elif event.type == pygame.FINGERDOWN and touch_id is None:
                touch_mode = True
                touch_id = event.finger_id
                pointer = (event.x * width, event.y * height)
                if game.cards:
                    pick_card(pointer)
                    pointer = (width / 2, height / 2)
                elif game.ended:
                    game = Game(config)
                    accumulator = 0
            elif event.type == pygame.FINGERMOTION and event.finger_id == touch_id:
                pointer = (event.x * width, event.y * height)
            elif event.type == pygame.FINGERUP and event.finger_id == touch_id:
                touch_id = None

        direction = (pointer[0] - width / 2, pointer[1] - height / 2)
        if touch_mode and touch_id is None:
            direction = (0, 0)
        if game.paused or game.ended or game.cards:
            accumulator = 0
        else:
            accumulator += frame_seconds
            while accumulator >= config["step_seconds"]:
                game.update(direction)
                accumulator -= config["step_seconds"]

        if effect_game is not game:
            effects.clear()
            shake_left = 0
            voice_wait = 0
            effect_game = game
            if pygame.mixer.get_init():
                pygame.mixer.stop()
        if not game.paused and not game.cards:
            for effect in effects:
                effect[4] -= frame_seconds
                if effect[0] != "death":
                    effect[2] -= feel["number_rise_speed"] * frame_seconds
            effects = [effect for effect in effects if effect[4] > 0]
            shake_left = max(0, shake_left - frame_seconds)
        played = set()
        voice_wait = max(0, voice_wait - frame_seconds)
        sound_wait = {name: max(0, wait - frame_seconds) for name, wait in sound_wait.items()}
        for kind, x, y, value in game.events:
            voice = {"level_up": "voice_level", "hurt": "voice_hurt",
                     "end": "voice_win" if game.victory else "voice_lose"}.get(kind)
            if voice in sounds and voice_channel is not None:
                if kind == "end" or (voice_wait <= 0 and not voice_channel.get_busy()):
                    voice_channel.play(sounds[voice])
                    voice_wait = config["sound"]["voice_cooldown"]
            if kind in sounds and kind not in played and sound_wait.get(kind, 0) <= 0:
                sounds[kind].play()
                played.add(kind)
                sound_wait[kind] = config["sound"]["cooldowns"].get(kind, 0)
            if kind in ("hit", "hurt", "death"):
                lifetime = feel["flash_seconds"] if kind == "death" else feel["number_seconds"]
                effects.append([kind, x, y, value, lifetime])
            if kind == "hurt":
                shake_left = feel["shake_seconds"]
        game.events.clear()
        shake = feel["shake_pixels"] * shake_left / feel["shake_seconds"]
        shake_x = round(visual_rng.uniform(-shake, shake))
        shake_y = round(visual_rng.uniform(-shake, shake))
        hero_center = (width // 2 - shake_x, height // 2 - shake_y)

        # World-to-screen conversion keeps the hero in the centre of the camera.
        camera_x, camera_y = game.x - width / 2 + shake_x, game.y - height / 2 + shake_y
        tile = pictures["floor"].get_width()
        for row in range(math.floor(camera_y / tile), math.floor((camera_y + height) / tile) + 1):
            for col in range(math.floor(camera_x / tile), math.floor((camera_x + width) / tile) + 1):
                screen.blit(pictures["floor"], (round(col * tile - camera_x), round(row * tile - camera_y)))
        if "ring" in game.weapons:
            pygame.draw.circle(screen, (180, 160, 85), hero_center, game.weapon_stats("ring")["radius"], 2)
        for gem in game.gems:
            picture = pictures["gem_blue" if gem.xp == 1 else "gem_pink"]
            screen.blit(picture, picture.get_rect(center=(round(gem.x - camera_x), round(gem.y - camera_y))))
        for x, y in game.blade_positions():
            picture = pictures["sword"]
            screen.blit(picture, picture.get_rect(center=(round(x - camera_x), round(y - camera_y))))
        for bat in game.bats:
            x, y = round(bat.x - camera_x), round(bat.y - camera_y)
            screen.blit(pictures[bat.kind], pictures[bat.kind].get_rect(center=(x, y)))
        for spark in game.sparks:
            pygame.draw.circle(screen, (255, 221, 105), (round(spark.x - camera_x), round(spark.y - camera_y)), config["weapons"]["spark"]["radius"])
        screen.blit(pictures["hero"], pictures["hero"].get_rect(center=hero_center))
        for kind, x, y, value, remaining in effects:
            position = (round(x - camera_x), round(y - camera_y))
            if kind == "death":
                radius = max(1, round(feel["flash_radius"] * remaining / feel["flash_seconds"]))
                pygame.draw.circle(screen, (255, 250, 210), position, radius)
            else:
                colour = (255, 100, 110) if kind == "hurt" else (255, 230, 125)
                label(f"-{value:g}", position, colour)
        pygame.draw.rect(screen, (13, 20, 28), (12, 12, 220, 82), border_radius=8)
        pygame.draw.rect(screen, (70, 35, 43), (22, 42, 200, 12))
        pygame.draw.rect(screen, (235, 83, 103), (22, 42, round(200 * game.hp / game.max_hp), 12))
        label(f"HP {game.hp} / {game.max_hp}", (22, 18))
        pygame.draw.rect(screen, (30, 45, 75), (22, 65, 200, 12))
        pygame.draw.rect(screen, (70, 150, 250), (22, 65, round(200 * min(1, game.xp / game.xp_needed)), 12))
        label(f"Lv {game.level}", (160, 18))
        seconds, total = int(game.elapsed), int(config["victory_seconds"])
        label(f"{seconds // 60}:{seconds % 60:02d} / {total // 60}:{total % 60:02d}", (250, 18))
        owned = list(game.weapons.items()) + [(n, v) for n, v in game.passives.items() if v]
        short = {"spark": "Spark", "blades": "Blades", "ring": "Ring", "boots": "Boots", "heart": "Heart", "magnet": "Magnet"}
        for row in range(0, len(owned), 3):
            label("   ".join(f"{short[n]} {v}" for n, v in owned[row:row + 3]), (16, height - 78 + row // 3 * 24))
        label("Move mouse / hold touch   •   P: pause", (16, height - 28))
        if game.paused or game.ended or game.cards:
            shade = pygame.Surface((width, height), pygame.SRCALPHA)
            shade.fill((6, 10, 20, 210))
            screen.blit(shade, (0, 0))
            if game.cards:
                label("LEVEL UP", (100, 100), big=True)
                for index, name in enumerate(game.cards):
                    rect = card_rects[index]
                    pygame.draw.rect(screen, (40, 65, 90), rect, border_radius=12)
                    level = game.weapons.get(name, game.passives.get(name, 0)) + 1
                    title = f"{names[name]} — Lv {level}" if name != "heal" else f"Heal {config['growth']['fallback_heal']} HP"
                    label(title, (rect.x + 14, rect.y + 24))
                    label(descriptions.get(name, "Restore health"), (rect.x + 14, rect.y + 65))
            else:
                label("VICTORY" if game.victory else "GAME OVER" if game.ended else "PAUSED", (width // 2 - 110, 265), big=True)
            if game.ended:
                seconds = int(game.elapsed)
                label(f"Time {seconds // 60}:{seconds % 60:02d}   Kills {game.kills}   Level {game.level}", (50, 325))
                label("Click or tap to play again", (85, 370))
            elif not game.cards:
                label("Press P to continue", (110, 330))
        pygame.display.flip()
        await asyncio.sleep(0)
    pygame.quit()


asyncio.run(main())
