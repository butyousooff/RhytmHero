import pygame
import sys

SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FPS = 60
LANES = 4
LANE_WIDTH = SCREEN_WIDTH // LANES
HIT_LINE_Y = SCREEN_HEIGHT - 100

KEYS = {pygame.K_q: 0, pygame.K_w: 1, pygame.K_e: 2, pygame.K_r: 3}
KEY_NAMES = ['Q', 'W', 'E', 'R']


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
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Rhythm Hero")
    clock = pygame.time.Clock()

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
                    print(f"Нажата дорожка {lane} ({KEY_NAMES[lane]})")

        screen.fill((0, 0, 0))
        draw_lanes(screen)
        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
