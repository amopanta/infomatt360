from app.services.form_compiler import form_compiler


def build_cert001_mini():
    fields = []
    for index in range(100):
        fields.append({"name": f"campo_{index}", "label": f"Campo {index}", "type": "number"})
    for index in range(5):
        fields.append({"name": f"repeat_{index}", "label": f"Repeat {index}", "type": "REPEAT"})
    for index in range(50):
        source = index % 100
        fields.append({"name": f"calc_{index}", "label": f"Calculo {index}", "type": "calculate", "config": {"calculate": f"${{campo_{source}}} + 1"}})
    return {"id": "cert001-mini", "name": "CERT-001 Mini", "fields": fields}


def test_cert001_mini_compiles_runtime_package():
    package = form_compiler.compile(build_cert001_mini())

    assert package.manifest.template_id == "cert001-mini"
    assert package.schema_.name == "CERT-001 Mini"
    assert package.performance_profile.fields == 155
    assert package.performance_profile.repeats == 5
    assert package.performance_profile.expressions == 50
    assert package.dependency_graph["campo_0"] == ["calc_0"]
    assert "calc_0.calculate" in package.expression_map
