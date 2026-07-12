from services.cli.datastreamctl import main


def test_capacity_plan_cli_can_plan_offline(capsys):
    assert main([
        "flink", "capacity-plan", "--partitions", "18", "--host-cpu", "24", "--host-memory-mb", "32768", "--json",
    ]) == 0
    output = capsys.readouterr().out
    assert '"parallelism": 18' in output
    assert '"taskmanager_replicas": 18' in output


def test_scaling_decision_cli_reports_hold(capsys):
    assert main([
        "flink", "scaling-decision", "--current-parallelism", "2", "--max-parallelism", "18", "--partitions", "18", "--lag", "100", "--busy-time", "0.5", "--json",
    ]) == 0
    assert '"action": "hold"' in capsys.readouterr().out
