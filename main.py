import pygame
import sys
import numpy as np

SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FPS = 60
LANES = 4
LANE_WIDTH = SCREEN_WIDTH // LANES
HIT_LINE_Y = SCREEN_HEIGHT - 100

KEYS = {pygame.K_q: 0, pygame.K_w: 1, pygame.K_e: 2, pygame.K_r: 3}
KEY_NAMES = ['Q', 'W', 'E', 'R']

hit_sounds = {}


def midi_to_freq(note_number):
    return 440 * (2 ** ((note_number - 69) / 12))


def generate_sound(frequency=440, duration=0.15, volume=0.4):
    sample_rate = 44100
    n_samples = int(sample_rate * duration)
    t = np.linspace(0, duration, n_samples, False)

    wave = np.sin(2 * np.pi * frequency * t)

    attack = int(n_samples * 0.1)
    decay = int(n_samples * 0.3)
    envelope = np.ones(n_samples)
    envelope[:attack] = np.linspace(0, 1, attack)
    envelope[-decay:] = np.linspace(1, 0, decay)

    wave = wave * envelope * volume
    audio = np.int16(wave * 32767)

    stereo = np.column_stack((audio, audio))
    return pygame.sndarray.make_sound(stereo)


def play_note_sound(note_number):
    if note_number not in hit_sounds:
        freq = midi_to_freq(note_number)
        hit_sounds[note_number] = generate_sound(freq)
        if len(hit_sounds) > 50:
            hit_sounds.pop(next(iter(hit_sounds)))

    if note_number in hit_sounds:
        hit_sounds[note_number].play()

def draw_lanes(screen):
    for i in range(LANES):
        x = i * LANE_WIDTH
        pygame.draw.line(screen, (60, 60, 80), (x, 0), (x, SCREEN_HEIGHT), 2)
        pygame.draw.rect(screen, (25, 25, 50), (x, HIT_LINE_Y, LANE_WIDTH, 100))
        pygame.draw.rect(screen, (80, 80, 120), (x, HIT_LINE_Y, LANE_WIDTH, 100), 2)
        font = pygame.font.Font(None, 52)
        text = font.render(KEY_NAMES[i], True, (220, 220, 255))
        text_rect = text.get_rect(center=(x + LANE_WIDTH // 2, HIT_LINE_Y + 50))
        screen.blit(text, text_rect)


def main():
    pygame.init()
    pygame.mixer.pre_init(44100, -16, 2, 512) 
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Rhythm Hero")
    clock = pygame.time.Clock()

    lane_notes = [60, 64, 67, 72]

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                if event.key in KEYS:
                    lane = KEYS[event.key]
                    note = lane_notes[lane]
                    print(f"Дорожка {lane}: нота {note} ({midi_to_freq(note):.1f} Hz)")
                    play_note_sound(note)

        screen.fill((0, 0, 0))
        draw_lanes(screen)
        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
