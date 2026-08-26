# SPDX-License-Identifier: MIT
"""Unit and integration tests for Bread-Bakers extraction script."""

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

from extract.breadbakers import (
    classify_message,
    preprocess_message,
    process_directory,
    process_single_file,
)


def test_preprocess_message():
    raw_message = (
        "--------------- MESSAGE bread-bakers.v096.n002.8 ---------------\n"
        "From: test@example.com\n"
        "Subject: Re: Bread Recipe\n"
        "Date: Sat, 30 Mar 96 07:07 CST\n"
        "\n"
        ">From: Quoted User <quoted@example.com>\n"
        ">Does anyone have a recipe?\n"
        "Here is a great recipe for Anadama Bread!\n"
        "  [Editor's Note:  I asked Bev about this recipe...]\n"
        "1 pk Yeast\n"
        "3 1/2 c Bread flour\n"
        "1/3 c Yellow cornmeal\n"
        "Rainbow V 1.19.1\n"
        "-- \n"
        "Bev in Mn\n"
        "bev@example.com\n"
    )

    cleaned = preprocess_message(raw_message)

    assert "--------------- MESSAGE" not in cleaned
    assert "From: test@example.com" not in cleaned
    assert ">From: Quoted User" not in cleaned
    assert "Editor's Note:" not in cleaned
    assert "Rainbow V 1.19.1" not in cleaned
    assert "Bev in Mn" not in cleaned  # Stripped by -- signature
    assert "1 pk Yeast" in cleaned
    assert "3 1/2 c Bread flour" in cleaned


def test_classify_message_samples():
    # 1. Recipe post
    recipe_text = (
        "ANADAMA BREAD - FOR 1-1/2 LB. LOAF-\n"
        "1 pk Yeast\n"
        "3 1/2 c Bread flour\n"
        "1/3 c Yellow cornmeal\n"
        "1 1/2 c Boiling water\n"
        "1/3 c Molasses\n"
        "1 ts Salt\n"
        "2 ts Butter\n"
        "Place cornmeal into a bowl. Carefully pour boiling water into cornmeal,\n"
        "stirring to make sure it is smooth. Let stand for about 30 minutes. Stir\n"
        "in molasses, salt and butter. Place yeast into the abm pan, bread flour,\n"
        "then cornmeal mixture. Select white bread and push start.\n"
    )
    reason, non_blank = classify_message(recipe_text, recipe_text)
    assert reason is None
    assert len(non_blank) > 10

    # 2. Too short
    short_text = (
        "My kids broke the paddle on my round Welbuilt breadmachine.\n"
        "How to replace?\n"
        "I know this has been posted before.\n"
    )
    reason, non_blank = classify_message(short_text, short_text)
    assert reason == "too_short"

    # 3. Table of contents
    toc_text = (
        "    001 - Reggie Dwork <reggie@regg - spring break\n"
        "    002 - RobLK6@aol.com            - broken paddle\n"
        "    003 - Gerard_Mcmahon@ftdetrck-c - re: baguette pan / malt syrup\n"
        "    004 - Doug Weller <eat@ramtops. - Re: rec.food.* CFV\n"
        "    005 - bj29@mirage.skypoint.com  - Re: bread-bakers-digest V6 #86\n"
    )
    reason, non_blank = classify_message(toc_text, toc_text)
    assert reason == "toc_only"

    # 4. Admin message
    admin_text = (
        "Welcome to bread-bakers mailing list!\n"
        "To unsubscribe from this list, send message to majordomo...\n"
        "BEGIN INFO bread-bakers\n"
    )
    reason, non_blank = classify_message(admin_text, admin_text)
    assert reason == "admin_only"

    # 5. No ingredients
    chat_text = (
        "I have been on this list for a little while and I love it.\n"
        "So far, what bread I make is done by hand, but I am considering\n"
        "buying a bread machine. I have read some of the remarks about\n"
        "different machines, but it seems like the Zo is the most popular.\n"
        "Now, the questions. Will the Zo make a heavy loaf?\n"
        "Does anyone have advice on which model to pick?\n"
        "I would appreciate any recommendations from list members.\n"
        "Also, what about replacement paddles for older models?\n"
        "Are they easy to find online or at hardware stores?\n"
        "Thanks in advance to everyone on the list!\n"
        "Hope you all have a wonderful weekend baking bread.\n"
    )
    reason, non_blank = classify_message(chat_text, chat_text)
    assert reason == "no_ingredients"


def test_process_single_file(tmp_path):
    recipe_file = tmp_path / "v096n002.txt-split-008"
    recipe_content = (
        "--------------- MESSAGE bread-bakers.v096.n002.8 ---------------\n"
        "From: bj29@mirage.skypoint.com (bjjan)\n"
        "Subject: Re: bread-bakers-digest V6 #87\n"
        "Date: Sat, 30 Mar 96 07:07 CST\n"
        "\n"
        "ANADAMA BREAD  - FOR 1-1/2 LB. LOAF-\n"
        "      1 pk Yeast\n"
        "  3 1/2 c  Bread flour\n"
        "    1/3 c  Yellow cornmeal\n"
        "  1 1/2 c  Boiling water\n"
        "    1/3 c  Molasses\n"
        "      1 ts Salt\n"
        "      2 ts Butter\n"
        "Place cornmeal into a bowl. Carefully pour boiling water into cornmeal,\n"
        "stirring to make sure it is smooth. Let stand for about 30 minutes. Stir\n"
        "in molasses, salt and butter. Place yeast into the abm pan, bread flour,\n"
        "then cornmeal mixture. Select white bread and push start.\n"
    )
    recipe_file.write_text(recipe_content, encoding="utf-8")

    out_dir = tmp_path / "out"
    out_dir.mkdir()

    res = process_single_file(recipe_file, out_dir)
    assert res is None  # Success, valid recipe

    saved_file = out_dir / "v096n002.txt-split-008.txt"
    assert saved_file.exists()
    saved_text = saved_file.read_text(encoding="utf-8")
    assert "From:" not in saved_text
    assert "1 pk Yeast" in saved_text


def test_process_directory(tmp_path):
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    report_csv = tmp_path / "failures.csv"
    in_dir.mkdir()

    # File 1: Recipe
    (in_dir / "msg1.txt").write_text(
        "ANADAMA BREAD  - FOR 1-1/2 LB. LOAF-\n"
        "      1 pk Yeast\n"
        "  3 1/2 c  Bread flour\n"
        "    1/3 c  Yellow cornmeal\n"
        "  1 1/2 c  Boiling water\n"
        "    1/3 c  Molasses\n"
        "      1 ts Salt\n"
        "      2 ts Butter\n"
        "Place cornmeal into a bowl. Stir to make sure it is smooth.\n"
        "Let stand for 30 minutes. Select white bread and push start.\n"
        "This is an old American recipe from DAK.\n",
        encoding="utf-8",
    )

    # File 2: Short chat
    (in_dir / "msg2.txt").write_text("Just a short chat line.\nHello world.\n")

    # File 3: TOC
    (in_dir / "msg3.txt").write_text(
        "    001 - Reggie Dwork <reggie@regg - spring break\n"
        "    002 - RobLK6@aol.com            - broken paddle\n"
        "    003 - Gerard_Mcmahon@ftdetrck-c - re: baguette pan / malt syrup\n"
        "    004 - Doug Weller <eat@ramtops. - Re: rec.food.* CFV\n"
    )

    recipes, failures = process_directory(in_dir, out_dir, report_csv, workers=1)
    assert recipes == 1
    assert failures == 2
    assert (out_dir / "msg1.txt").exists()

    assert report_csv.exists()
    with report_csv.open("r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
        assert len(reader) == 2
        reasons = {r["reason"] for r in reader}
        assert "too_short" in reasons
        assert "toc_only" in reasons


def test_integration_with_convert(tmp_path):
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    report_csv = tmp_path / "failures.csv"
    in_dir.mkdir()

    sample_src = Path(
        "/home/alex/junk/Recipes/Ingest/ToDo/TXT/breadbakers/split/v096n002.txt-split-008"
    )
    if not sample_src.exists():
        pytest.skip("Sample file not present in repository")

    (in_dir / sample_src.name).write_text(
        sample_src.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8"
    )

    recipes, failures = process_directory(in_dir, out_dir, report_csv, workers=1)
    assert recipes == 1

    converted_json = tmp_path / "converted.json"
    cmd = [
        sys.executable,
        "convert.py",
        str(out_dir),
        "-o",
        str(converted_json),
        "--no-nlp",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert converted_json.exists()

    with converted_json.open("r", encoding="utf-8") as f:
        data = json.load(f)
        assert len(data) >= 1
        assert data[0].get("@type") == "Recipe"
