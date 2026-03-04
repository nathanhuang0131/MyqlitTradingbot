from game.systems.battle import formulas


def test_hit_chance_bounds():
    assert 0.05 <= formulas.hit_chance(1, 100) <= 0.98
    assert 0.05 <= formulas.hit_chance(100, 1) <= 0.98


def test_physical_damage_positive():
    assert formulas.physical_damage(10, 50, 10) >= 1


def test_exp_curve_increasing():
    assert formulas.exp_curve(2) > formulas.exp_curve(1)
    assert formulas.exp_curve(3) > formulas.exp_curve(2)


def test_skill_power_scaling_modes():
    base = formulas.skill_power(10, 5)
    fast = formulas.skill_power(10, 5, fast_scaling=True)
    hard = formulas.skill_power(10, 5, fast_scaling=True, hard_scaling=True)
    assert fast > base
    assert hard > fast
