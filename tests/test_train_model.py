from train_model import build_training_text, cut_text


def test_build_training_text_merges_fields():
    row = {
        "title": "高等数学 极限",
        "tag_names": "高数,极限",
        "tags": "同济第七版",
        "desc": "讲解洛必达法则",
        "source_keyword": "高等数学 同济第五版",
    }
    text = build_training_text(row)
    assert "高等数学" in text
    assert "洛必达" in text
    assert "同济" in text


def test_cut_text_outputs_space_separated_tokens():
    cut = cut_text("线性代数 矩阵 乘法")
    assert isinstance(cut, str)
    assert " " in cut or cut == ""

