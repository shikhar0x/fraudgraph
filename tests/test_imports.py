def test_application_imports():
    import actions.policy.engine
    import actions.sar
    import agent.graphrag.bundle
    import agent.reasoning.graph
    import app.config
    import app.ingest
    import app.run_benchmark
    import case_memory.schema
    import graph.factory
    import graph.ingestion.pipeline
    import validation.validator

    assert app.config.get_settings().mode in {"local", "tigergraph"}


def test_twenty_case_files_exist_and_validate():
    from pathlib import Path

    from validation.validator import validate_case_record

    cases = sorted(Path("cases").glob("HHG-*.json"))
    assert [p.stem for p in cases] == [f"HHG-{i:03d}" for i in range(1, 21)]
    for path in cases:
        import json

        errs = validate_case_record(json.loads(path.read_text(encoding="utf-8")))
        assert errs == [], (path.name, errs)
