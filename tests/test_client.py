import pytest

from crux_mcp.client import (
    CruxClient,
    CruxError,
    Target,
    assess,
    summarise_history,
    summarise_record,
)


class TestTarget:
    def test_url_wins_nothing_when_both_given(self):
        with pytest.raises(CruxError, match="not both"):
            Target(origin="https://a.com", url="https://a.com/x").payload()

    def test_requires_one(self):
        with pytest.raises(CruxError, match="either origin or url"):
            Target().payload()

    def test_origin(self):
        assert Target(origin="https://a.com").payload() == {"origin": "https://a.com"}

    def test_url(self):
        assert Target(url="https://a.com/x").payload() == {"url": "https://a.com/x"}


class TestAssess:
    @pytest.mark.parametrize(
        "metric,value,expected",
        [
            ("largest_contentful_paint", 2000, "good"),
            ("largest_contentful_paint", 2500, "good"),  # boundary is inclusive
            ("largest_contentful_paint", 3000, "needs-improvement"),
            ("largest_contentful_paint", 5000, "poor"),
            ("interaction_to_next_paint", 150, "good"),
            ("interaction_to_next_paint", 600, "poor"),
            ("cumulative_layout_shift", 0.05, "good"),
            ("cumulative_layout_shift", 0.3, "poor"),
            ("largest_contentful_paint", None, "unknown"),
            ("not_a_metric", 1, "unknown"),
        ],
    )
    def test_thresholds(self, metric, value, expected):
        assert assess(metric, value) == expected


class TestFormFactor:
    def test_all_omits_the_filter(self):
        assert CruxClient._form_factor("ALL") == {}

    def test_none_omits_the_filter(self):
        assert CruxClient._form_factor(None) == {}

    def test_normalises_case(self):
        assert CruxClient._form_factor("phone") == {"formFactor": "PHONE"}

    def test_rejects_unknown(self):
        with pytest.raises(CruxError, match="form_factor must be"):
            CruxClient._form_factor("WATCH")


class TestMissingKey:
    def test_explains_that_oauth_is_not_accepted(self):
        client = CruxClient(api_key="")
        with pytest.raises(CruxError, match="does not accept OAuth"):
            client.record(Target(origin="https://a.com"))


RECORD = {
    "record": {
        "key": {"origin": "https://a.com"},
        "collectionPeriod": {"lastDate": {"year": 2026, "month": 8, "day": 10}},
        "metrics": {
            "largest_contentful_paint": {
                "percentiles": {"p75": 1642},
                "histogram": [
                    {"density": 0.81},
                    {"density": 0.13},
                    {"density": 0.06},
                ],
            },
            "cumulative_layout_shift": {"percentiles": {"p75": "0.01"}},
            "interaction_to_next_paint": {"percentiles": {"p75": 145}},
        },
    }
}


class TestSummariseRecord:
    def test_extracts_p75_and_assessment(self):
        out = summarise_record(RECORD)
        assert out["metrics"]["largest_contentful_paint"]["p75"] == 1642
        assert out["metrics"]["largest_contentful_paint"]["assessment"] == "good"

    def test_handles_string_p75(self):
        # CLS comes back as a string from the API.
        assert out_cls(RECORD) == "good"

    def test_distribution_when_histogram_present(self):
        dist = summarise_record(RECORD)["metrics"]["largest_contentful_paint"]["distribution"]
        assert dist["good"] == 0.81
        assert dist["poor"] == 0.06

    def test_overall_pass(self):
        assert summarise_record(RECORD)["core_web_vitals_pass"] is True

    def test_overall_fail_when_one_metric_poor(self):
        bad = {
            "record": {
                "metrics": {
                    "largest_contentful_paint": {"percentiles": {"p75": 6000}},
                    "cumulative_layout_shift": {"percentiles": {"p75": "0.01"}},
                    "interaction_to_next_paint": {"percentiles": {"p75": 145}},
                }
            }
        }
        assert summarise_record(bad)["core_web_vitals_pass"] is False

    def test_no_metrics_is_not_a_pass(self):
        assert summarise_record({"record": {"metrics": {}}})["core_web_vitals_pass"] is False


def out_cls(record):
    return summarise_record(record)["metrics"]["cumulative_layout_shift"]["assessment"]


HISTORY = {
    "record": {
        "collectionPeriods": [
            {"lastDate": {"year": 2026, "month": 7, "day": 27}},
            {"lastDate": {"year": 2026, "month": 8, "day": 3}},
        ],
        "metrics": {
            "largest_contentful_paint": {"percentilesTimeseries": {"p75s": [2600, 2100]}}
        },
    }
}


class TestSummariseHistory:
    def test_weeks_are_iso_dates(self):
        assert summarise_history(HISTORY)["weeks"] == ["2026-07-27", "2026-08-03"]

    def test_series_pairs_values_with_weeks(self):
        series = summarise_history(HISTORY)["metrics"]["largest_contentful_paint"]
        assert series[0] == {
            "week_ending": "2026-07-27",
            "p75": 2600,
            "assessment": "needs-improvement",
        }
        assert series[1]["assessment"] == "good"
