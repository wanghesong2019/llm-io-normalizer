from llm_io_normalizer.normalizers import extract_json_object


def test_extract_json_object_plain():
    assert extract_json_object('{"结果": 2}') == {"结果": 2}


def test_extract_json_object_fenced():
    assert extract_json_object('```json\n{"结果": 0}\n```') == {"结果": 0}


def test_extract_json_object_embedded():
    assert extract_json_object('分析如下 {"结果": 1} 结束') == {"结果": 1}
