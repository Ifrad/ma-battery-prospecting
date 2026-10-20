from prospect.priors import config


def test_every_utility_has_schedules_or_a_placeholder_charge():
    utilities = config.load()["rates"]["utilities"]
    assert len(utilities) == 8
    for name, utility in utilities.items():
        if "schedules" not in utility:
            assert utility["demand_charge_per_kw_month"]["status"] == "placeholder", (
                name
            )
            continue
        for s in utility["schedules"]:
            assert s["demand_charge_per_kw_month"] >= 0, (name, s["name"])
            assert s["eligibility"], (name, s["name"])
            assert s["status"] == "sourced", (name, s["name"])
