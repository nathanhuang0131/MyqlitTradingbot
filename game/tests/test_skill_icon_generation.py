from pathlib import Path

from game.tools.generate_skill_icons import generate_skill_icons


def test_generate_skill_icons_creates_one_file_per_skill(tmp_path: Path):
    skills_csv = tmp_path / "skills.csv"
    out_dir = tmp_path / "icons"
    skills_csv.write_text(
        "id,name,skill_type,power,mp_cost,hit_rate,status_effect\n"
        "slash,Slash,physical,10,0,0.95,\n"
        "firebolt,Firebolt,magic,13,6,0.92,burn\n",
        encoding="utf-8",
    )

    generated = generate_skill_icons(skills_csv=skills_csv, output_dir=out_dir)

    assert {p.stem for p in generated} == {"slash", "firebolt"}
    for icon in generated:
        assert icon.exists()
