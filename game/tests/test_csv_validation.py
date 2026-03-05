from pathlib import Path

from game.tools import validate_csv


def _write_required_csvs(csv_dir: Path) -> None:
    (csv_dir / "classes.csv").write_text("id,name,hp,mp,atk,defense,mag,mdef,agi,luck\nwarrior,Warrior,100,20,10,8,2,3,5,2\n", encoding="utf-8")
    (csv_dir / "characters.csv").write_text("id,name,class_id,faction,role,is_special\np,Player,warrior,ally,hero,false\n", encoding="utf-8")
    (csv_dir / "skills.csv").write_text("id,name,skill_type,power,mp_cost,hit_rate,status_effect\nslash,Slash,physical,10,0,1.0,\n", encoding="utf-8")
    (csv_dir / "monsters.csv").write_text("id,name,hp,mp,atk,defense,mag,mdef,agi,luck,exp,gold,drops\ngoblin,Goblin,10,0,5,2,1,1,3,1,5,5,potion\n", encoding="utf-8")
    (csv_dir / "artifacts.csv").write_text("id,name,owner_hint,unique,craftable\na,Artifact,none,true,false\n", encoding="utf-8")
    (csv_dir / "events.csv").write_text(
        "id,map_id,x,y,trigger,flag_set,flag_required,once,dialogue_start_id,encounter_id,recruit_id,next_event_id,chapter\n"
        "ev1,starter_field,3,3,on_enter,flag_a,,true,D1,,, ,1\n",
        encoding="utf-8",
    )
    (csv_dir / "dialogue.csv").write_text(
        "id,speaker,text,next_id,choice_group,choice_label,flag_required,set_flag,affection_delta,trust_delta,item_id,item_delta\n"
        "D1,Narrator,Hello,,,,,,,,,\n",
        encoding="utf-8",
    )
    (csv_dir / "gifts.csv").write_text("id,item_id,target_npc,affection_delta,trust_delta\nG1,gift,lady_airi,5,5\n", encoding="utf-8")
    (csv_dir / "relationships.csv").write_text("npc_id,likes,dislikes,bond1,bond2,bond3,duo_skill\nlady_airi,gift,bad,20,40,60,DUO_AIRI\n", encoding="utf-8")
    (csv_dir / "routes.csv").write_text("id,name,win_condition,lose_condition,start_flags\nordinary,Ordinary,w,l,f\n", encoding="utf-8")
    (csv_dir / "bond_thresholds.csv").write_text("bond_level,min_affection,min_trust\n1,10,10\n", encoding="utf-8")
    (csv_dir / "skill_progression.csv").write_text("class_id,level,skill_id\nwarrior,1,slash\n", encoding="utf-8")


def test_validator_catches_invalid_dialogue_next_id(tmp_path: Path):
    csv_dir = tmp_path / "csv"
    csv_dir.mkdir()
    _write_required_csvs(csv_dir)

    (csv_dir / "dialogue.csv").write_text(
        "id,speaker,text,next_id,choice_group,choice_label,flag_required,set_flag,affection_delta,trust_delta,item_id,item_delta\n"
        "D1,Narrator,Hello,D999,,,,,,,,\n",
        encoding="utf-8",
    )

    exit_code, errors = validate_csv.validate(csv_dir=csv_dir)
    assert exit_code == 1
    assert any("next_id" in e for e in errors)


def test_validator_catches_missing_skill_reference_in_skill_progression(tmp_path: Path):
    csv_dir = tmp_path / "csv"
    csv_dir.mkdir()
    _write_required_csvs(csv_dir)
    (csv_dir / "skill_progression.csv").write_text("class_id,level,skill_id\nwarrior,1,missing_skill\n", encoding="utf-8")

    exit_code, errors = validate_csv.validate(csv_dir=csv_dir)
    assert exit_code == 1
    assert any("missing skill" in e for e in errors)


def test_validator_catches_unknown_encounter_id(tmp_path: Path):
    csv_dir = tmp_path / "csv"
    csv_dir.mkdir()
    _write_required_csvs(csv_dir)
    (csv_dir / "events.csv").write_text(
        "id,map_id,x,y,trigger,flag_set,flag_required,once,dialogue_start_id,encounter_id,recruit_id,next_event_id,chapter\n"
        "ev1,starter_field,3,3,on_enter,flag_a,,true,D1,unknown_enc,,,1\n",
        encoding="utf-8",
    )

    exit_code, errors = validate_csv.validate(csv_dir=csv_dir)
    assert exit_code == 1
    assert any("encounter_id references missing encounter table id" in e for e in errors)
