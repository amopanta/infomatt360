from app.services.form_compiler import form_compiler


def make_template(field_count: int, calc_count: int = 0, repeat_count: int = 0):
    fields = []
    for index in range(field_count):
        fields.append({"name": f"campo_{index}", "label": f"Campo {index}", "type": "text"})
    for index in range(calc_count):
        fields.append({"name": f"calc_{index}", "label": f"Calc {index}", "type": "calculate", "config": {"calculate": "${campo_0} + 1"}})
    for index in range(repeat_count):
        fields.append({"name": f"repeat_{index}", "label": f"Repeat {index}", "type": "REPEAT"})
    return {"id": "tpl-profile", "name": "Profile Test", "fields": fields}


def test_low_complexity_profile():
    package = form_compiler.compile(make_template(10))
    assert package.performance_profile.complexity == "LOW"


def test_medium_complexity_profile():
    package = form_compiler.compile(make_template(100, calc_count=10))
    assert package.performance_profile.complexity == "MEDIUM"


def test_high_complexity_profile():
    package = form_compiler.compile(make_template(220, calc_count=120, repeat_count=6))
    assert package.performance_profile.complexity == "HIGH"
    assert "Activar render por seccion" in package.performance_profile.recommendations
