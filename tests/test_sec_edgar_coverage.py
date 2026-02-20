"""Tests for app/pipelines/sec_edgar.py to achieve ≥80% coverage."""
import asyncio
import time
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call
from tempfile import TemporaryDirectory

from app.pipelines.sec_edgar import RateLimiter, SECEdgarPipeline


# ---------------------------------------------------------------------------
# RateLimiter
# ---------------------------------------------------------------------------

class TestRateLimiter:
    """Tests for RateLimiter."""

    def test_init_default(self):
        rl = RateLimiter()
        assert rl.min_interval == pytest.approx(1.0 / 8.0)
        assert rl.last_request_time == 0.0

    def test_init_custom_rate(self):
        rl = RateLimiter(requests_per_second=4.0)
        assert rl.min_interval == pytest.approx(0.25)

    def test_wait_updates_last_request_time(self):
        rl = RateLimiter(requests_per_second=100.0)
        before = time.time()
        rl.wait()
        assert rl.last_request_time >= before

    def test_wait_no_sleep_when_fast_enough(self):
        """If enough time has passed, no sleep is needed."""
        rl = RateLimiter(requests_per_second=1.0)
        rl.last_request_time = 0.0  # very old last request
        with patch("app.pipelines.sec_edgar.time.sleep") as mock_sleep:
            rl.wait()
        mock_sleep.assert_not_called()

    def test_wait_sleeps_when_too_fast(self):
        """If called twice in rapid succession, sleep is triggered."""
        rl = RateLimiter(requests_per_second=1.0)
        rl.last_request_time = time.time()  # just now
        with patch("app.pipelines.sec_edgar.time.sleep") as mock_sleep:
            rl.wait()
        mock_sleep.assert_called_once()
        sleep_arg = mock_sleep.call_args[0][0]
        assert sleep_arg > 0

    def test_wait_async_updates_last_request_time(self):
        rl = RateLimiter(requests_per_second=100.0)
        before = time.time()
        asyncio.get_event_loop().run_until_complete(rl.wait_async())
        assert rl.last_request_time >= before

    def test_wait_async_sleeps_when_too_fast(self):
        rl = RateLimiter(requests_per_second=1.0)
        rl.last_request_time = time.time()

        async def _run():
            with patch("app.pipelines.sec_edgar.asyncio.sleep") as mock_sleep:
                mock_sleep.return_value = None
                await rl.wait_async()
                mock_sleep.assert_called_once()

        asyncio.get_event_loop().run_until_complete(_run())


# ---------------------------------------------------------------------------
# SECEdgarPipeline
# ---------------------------------------------------------------------------

class TestSECEdgarPipeline:
    """Tests for SECEdgarPipeline."""

    @pytest.fixture
    def tmp_dir(self, tmp_path):
        return tmp_path

    @pytest.fixture
    def pipeline(self, tmp_dir):
        """Create pipeline with mocked Downloader."""
        with patch("app.pipelines.sec_edgar.Downloader") as mock_dl_cls:
            mock_dl_cls.return_value = MagicMock()
            p = SECEdgarPipeline(
                company_name="TestOrg",
                email="test@example.com",
                download_dir=tmp_dir,
                requests_per_second=100.0,  # No actual rate limiting in tests
                max_retries=2,
                retry_delay=0.0,
            )
            yield p, mock_dl_cls.return_value

    def test_init_creates_download_dir(self, tmp_path):
        new_dir = tmp_path / "sec_test"
        with patch("app.pipelines.sec_edgar.Downloader"):
            p = SECEdgarPipeline("Org", "a@b.com", download_dir=new_dir)
        assert new_dir.exists()

    def test_download_filings_success(self, pipeline, tmp_path):
        """Test successful filing download returns file paths."""
        p, mock_dl = pipeline

        # Create mock filing files in expected location
        ticker = "AAPL"
        filing_type = "10-K"
        filing_dir = p.download_dir / "sec-edgar-filings" / ticker / filing_type
        filing_dir.mkdir(parents=True)
        full_sub = filing_dir / "0001/full-submission.txt"
        full_sub.parent.mkdir(parents=True)
        full_sub.write_text("filing content")

        mock_dl.get.return_value = None  # Success

        with patch("app.pipelines.sec_edgar.time.sleep"):
            result = p.download_filings(ticker, filing_types=[filing_type], limit=1)

        assert len(result) == 1
        assert result[0] == full_sub

    def test_download_filings_empty_when_no_files(self, pipeline):
        """Test download returns empty list when no files exist."""
        p, mock_dl = pipeline
        mock_dl.get.return_value = None

        with patch("app.pipelines.sec_edgar.time.sleep"):
            result = p.download_filings("AAPL", filing_types=["10-K"], limit=1)

        assert result == []

    def test_download_filings_retry_on_rate_limit(self, pipeline):
        """Test that rate limit errors trigger retries."""
        p, mock_dl = pipeline
        p.retry_delay = 0.0

        mock_dl.get.side_effect = [
            Exception("429 rate limit exceeded"),
            None,  # success on retry
        ]

        with patch("app.pipelines.sec_edgar.time.sleep"):
            result = p.download_filings("AAPL", filing_types=["10-K"], limit=1)

        assert mock_dl.get.call_count == 2

    def test_download_filings_all_retries_fail(self, pipeline):
        """Test that all retries failing results in empty list for that type."""
        p, mock_dl = pipeline
        mock_dl.get.side_effect = Exception("network error")

        with patch("app.pipelines.sec_edgar.time.sleep"):
            result = p.download_filings("AAPL", filing_types=["10-K"], limit=1)

        assert result == []
        assert mock_dl.get.call_count == p.max_retries

    def test_download_filings_filing_type_mapping(self, pipeline):
        """Test DEF-14A maps to DEFA14A for the library."""
        p, mock_dl = pipeline
        mock_dl.get.return_value = None

        with patch("app.pipelines.sec_edgar.time.sleep"):
            p.download_filings("AAPL", filing_types=["DEF-14A"], limit=1)

        # Library should be called with DEFA14A
        call_args = mock_dl.get.call_args
        assert call_args[0][0] == "DEFA14A"

    def test_download_filings_primary_documents(self, pipeline, tmp_path):
        """Test that primary-document.* files are also collected."""
        p, mock_dl = pipeline
        ticker = "MSFT"
        filing_type = "10-Q"
        filing_dir = p.download_dir / "sec-edgar-filings" / ticker / filing_type
        accession = filing_dir / "0001"
        accession.mkdir(parents=True)

        (accession / "full-submission.txt").write_text("content")
        (accession / "primary-document.htm").write_text("<html></html>")

        mock_dl.get.return_value = None

        with patch("app.pipelines.sec_edgar.time.sleep"):
            result = p.download_filings(ticker, filing_types=[filing_type], limit=1)

        assert len(result) == 2

    def test_get_filing_path_exists(self, pipeline, tmp_path):
        """Test get_filing_path returns path when directory exists."""
        p, _ = pipeline
        ticker = "AAPL"
        filing_type = "10-K"
        dir_ = p.download_dir / "sec-edgar-filings" / ticker / filing_type
        dir_.mkdir(parents=True)

        result = p.get_filing_path(ticker, filing_type)
        assert result == dir_

    def test_get_filing_path_not_exists(self, pipeline):
        """Test get_filing_path returns None when directory doesn't exist."""
        p, _ = pipeline
        result = p.get_filing_path("ZZZZ", "10-K")
        assert result is None

    def test_get_filing_path_type_mapping(self, pipeline, tmp_path):
        """Test DEF-14A mapping in get_filing_path."""
        p, _ = pipeline
        dir_ = p.download_dir / "sec-edgar-filings" / "AAPL" / "DEFA14A"
        dir_.mkdir(parents=True)

        result = p.get_filing_path("AAPL", "DEF-14A")
        assert result == dir_

    def test_list_downloaded_filings_empty(self, pipeline):
        """Test list_downloaded_filings returns empty when base dir missing."""
        p, _ = pipeline
        result = p.list_downloaded_filings()
        assert result == []

    def test_list_downloaded_filings_all(self, pipeline, tmp_path):
        """Test listing all downloaded filings."""
        p, _ = pipeline
        base = p.download_dir / "sec-edgar-filings" / "AAPL" / "10-K" / "0001"
        base.mkdir(parents=True)
        f = base / "full-submission.txt"
        f.write_text("content")

        result = p.list_downloaded_filings()
        assert len(result) == 1
        assert result[0] == f

    def test_list_downloaded_filings_filtered_by_ticker(self, pipeline, tmp_path):
        """Test listing filings filtered by ticker."""
        p, _ = pipeline
        for ticker in ["AAPL", "MSFT"]:
            d = p.download_dir / "sec-edgar-filings" / ticker / "10-K" / "0001"
            d.mkdir(parents=True)
            (d / "full-submission.txt").write_text("content")

        result = p.list_downloaded_filings(ticker="AAPL")
        assert len(result) == 1
        assert "AAPL" in str(result[0])

    def test_download_all_companies(self, pipeline, tmp_path):
        """Test download_all_companies processes multiple tickers."""
        p, mock_dl = pipeline
        mock_dl.get.return_value = None

        with patch("app.pipelines.sec_edgar.time.sleep"):
            result = p.download_all_companies(
                tickers=["AAPL", "MSFT"],
                filing_types=["10-K"],
                limit=1,
                delay_between_companies=0.0,
            )

        assert "AAPL" in result
        assert "MSFT" in result

    def test_download_all_companies_error_handled(self, pipeline):
        """Test download_all_companies handles per-company errors gracefully."""
        p, mock_dl = pipeline
        mock_dl.get.side_effect = RuntimeError("unexpected error")

        with patch("app.pipelines.sec_edgar.time.sleep"):
            result = p.download_all_companies(
                tickers=["AAPL"],
                filing_types=["10-K"],
                limit=1,
                delay_between_companies=0.0,
            )

        # Should not raise; returns empty list for failed ticker
        assert result["AAPL"] == []

    def test_download_filings_async(self, pipeline):
        """Test async download delegates to synchronous download_filings."""
        p, mock_dl = pipeline
        mock_dl.get.return_value = None

        async def _run():
            with patch("app.pipelines.sec_edgar.time.sleep"):
                return await p.download_filings_async("AAPL", filing_types=["10-K"], limit=1)

        result = asyncio.get_event_loop().run_until_complete(_run())
        assert isinstance(result, list)
