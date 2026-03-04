from __future__ import annotations

from game.settings import GRID_HEIGHT, GRID_WIDTH


def starter_grid() -> list[list[str]]:
    grid = [["grass" for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]
    for x in range(7, 18):
        grid[8][x] = "danger"
    grid[3][3] = "town"
    grid[12][20] = "dungeon"
    grid[6][16] = "shrine"
    grid[2][20] = "kings_road"
    return grid
