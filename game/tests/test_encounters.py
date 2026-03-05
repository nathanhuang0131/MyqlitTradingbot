from game.assets.core.rng import RNGService
from game.systems.encounter import EncounterSystem
from game.world.events import roll_danger_encounter


def test_danger_encounter_is_deterministic_with_seed():
    rng_a = RNGService(123)
    rng_b = RNGService(123)
    seq_a = [roll_danger_encounter(rng_a, 0.15) for _ in range(20)]
    seq_b = [roll_danger_encounter(rng_b, 0.15) for _ in range(20)]
    assert seq_a == seq_b


def test_encounter_system_tracks_roll_debug_data():
    rng = RNGService(42)
    encounters = EncounterSystem(chance=1.0, danger_tiles={"danger"})

    triggered = encounters.roll_for_tile("danger", rng)

    assert triggered is True
    assert encounters.last_tile_id == "danger"
    assert encounters.last_is_danger is True
    assert encounters.last_roll is not None
    assert encounters.last_triggered is True


def test_force_encounter_triggers_once_on_next_move():
    rng = RNGService(1)
    encounters = EncounterSystem(chance=0.0, danger_tiles={"danger"})
    encounters.force_next_encounter()

    first = encounters.roll_for_tile("grass", rng)
    second = encounters.roll_for_tile("grass", rng)

    assert first is True
    assert second is False
