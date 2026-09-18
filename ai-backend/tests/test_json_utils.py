"""json_utils.extract_json：模型输出千奇百怪，这层必须扛住。"""
from app.core.json_utils import extract_json


def test_plain_json():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_json_in_markdown_fence():
    raw = '好的，这是结果：\n```json\n{"title": "路线图", "n": 2}\n```\n希望有帮助。'
    assert extract_json(raw) == {"title": "路线图", "n": 2}


def test_json_with_surrounding_prose():
    raw = '下面是我的回答：{"ready": true} 以上。'
    assert extract_json(raw) == {"ready": True}


def test_trailing_comma_tolerated():
    assert extract_json('{"a": 1, "b": [1, 2,],}') == {"a": 1, "b": [1, 2]}


def test_braces_inside_string_do_not_break_pairing():
    raw = '{"note": "这里有个 { 花括号 } 在字符串里", "ok": true}'
    assert extract_json(raw) == {"note": "这里有个 { 花括号 } 在字符串里", "ok": True}


def test_escaped_quote_inside_string():
    raw = r'{"note": "他说 \"你好\"", "ok": true}'
    assert extract_json(raw) == {"note": '他说 "你好"', "ok": True}


def test_top_level_array():
    assert extract_json("结果：[1, 2, 3]") == [1, 2, 3]


def test_garbage_returns_none():
    assert extract_json("模型今天不想输出 JSON") is None
    assert extract_json("") is None
    assert extract_json("{不是合法 JSON") is None


def test_nested_object_returns_outermost():
    raw = '{"stages": [{"tasks": [{"id": "t-1-1"}]}], "final_outcome": "Demo"}'
    data = extract_json(raw)
    assert data["stages"][0]["tasks"][0]["id"] == "t-1-1"
