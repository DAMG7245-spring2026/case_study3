"""SEC EDGAR filing download pipeline with rate limiting."""

import asyncio
import logging
import time
from pathlib import Path
from typing import Optional

from sec_edgar_downloader import Downloader

logger = logging.getLogger(__name__)

# sec_edgar_downloader expects "DEFA14A" (no hyphen), not "DEF-14A"
FILING_TYPE_TO_LIBRARY: dict[str, str] = {"DEF-14A": "DEFA14A"}


class RateLimiter:
    """Simple rate limiter for SEC EDGAR API (10 requests/second max)."""
    
    def __init__(self, requests_per_second: float = 8.0):
        """
        Initialize rate limiter.
        
        Args:
            requests_per_second: Max requests per second (default 8 to be safe, SEC allows 10)
        """
        self.min_interval = 1.0 / requests_per_second
        self.last_request_time = 0.0
    
    def wait(self):
        """Wait if necessary to respect rate limit."""
        now = time.time()
        elapsed = now - self.last_request_time
        
        if elapsed < self.min_interval:
            sleep_time = self.min_interval - elapsed
            logger.debug(f"Rate limiting: sleeping {sleep_time:.3f}s")
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    async def wait_async(self):
        """Async version of wait."""
        now = time.time()
        elapsed = now - self.last_request_time
        
        if elapsed < self.min_interval:
            sleep_time = self.min_interval - elapsed
            logger.debug(f"Rate limiting: sleeping {sleep_time:.3f}s")
            await asyncio.sleep(sleep_time)
        
        self.last_request_time = time.time()


class SECEdgarPipeline:
    """Pipeline for downloading SEC filings from EDGAR with rate limiting."""

    def __init__(
        self,
        company_name: str,
        email: str,
        download_dir: Path = Path("data/raw/sec"),
        requests_per_second: float = 8.0,  # Conservative (SEC allows 10)
        max_retries: int = 3,
        retry_delay: float = 5.0
    ):
        """
        Initialize the SEC EDGAR pipeline.
        
        Args:
            company_name: Your company/organization name (required by SEC)
            email: Your email address (required by SEC)
            download_dir: Directory to store downloaded filings
            requests_per_second: Rate limit (default 8, SEC max is 10)
            max_retries: Number of retries on failure
            retry_delay: Seconds to wait between retries
        """
        self.download_dir = download_dir
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
        self.dl = Downloader(company_name, email, str(download_dir))
        self.rate_limiter = RateLimiter(requests_per_second)
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        logger.info(f"SEC EDGAR Pipeline initialized (rate limit: {requests_per_second} req/s)")

    def download_filings(
        self,
        ticker: str,
        filing_types: list[str] = ["10-K", "10-Q", "8-K"],
        limit: int = 10,
        after: str = "2021-01-01",
        before: Optional[str] = None
    ) -> list[Path]:
        """
        Download SEC filings for a company with rate limiting and retry logic.
        
        Args:
            ticker: Company ticker symbol (e.g., "AAPL")
            filing_types: List of filing types to download
            limit: Maximum number of filings per type
            after: Only download filings after this date (YYYY-MM-DD)
            before: Only download filings before this date (YYYY-MM-DD)
            
        Returns:
            List of paths to downloaded filing files
        """
        downloaded = []
        
        for filing_type in filing_types:
            library_form = FILING_TYPE_TO_LIBRARY.get(filing_type, filing_type)
            # Rate limit before each filing type request
            self.rate_limiter.wait()
            
            success = False
            last_error = None
            
            for attempt in range(1, self.max_retries + 1):
                try:
                    logger.info(f"Downloading {filing_type} for {ticker} (attempt {attempt}/{self.max_retries})")
                    
                    # Download filings (download_details=True to get PDF/HTML primary documents)
                    # Library expects DEFA14A, not DEF-14A
                    self.dl.get(
                        library_form,
                        ticker,
                        limit=limit,
                        after=after,
                        before=before,
                        download_details=True
                    )
                    
                    success = True
                    break
                    
                except Exception as e:
                    last_error = e
                    error_msg = str(e).lower()
                    
                    # Check if it's a rate limit error
                    if "rate" in error_msg or "429" in error_msg or "too many" in error_msg:
                        wait_time = self.retry_delay * attempt  # Exponential backoff
                        logger.warning(f"Rate limited! Waiting {wait_time}s before retry...")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"Error downloading {filing_type} for {ticker}: {e}")
                        if attempt < self.max_retries:
                            time.sleep(self.retry_delay)
            
            if not success:
                logger.error(f"Failed to download {filing_type} for {ticker} after {self.max_retries} attempts: {last_error}")
                continue
            
            # Find downloaded files (library writes to directory named with library form, e.g. DEFA14A)
            filing_dir = self.download_dir / "sec-edgar-filings" / ticker / library_form
            
            if filing_dir.exists():
                for filing_path in filing_dir.glob("**/full-submission.txt"):
                    if filing_path not in downloaded:
                        downloaded.append(filing_path)
                        logger.info(f"Downloaded: {filing_path}")
                
                for filing_path in filing_dir.glob("**/primary-document.*"):
                    if filing_path not in downloaded:
                        downloaded.append(filing_path)
                        logger.info(f"Downloaded: {filing_path}")
                        
        logger.info(f"Total downloaded for {ticker}: {len(downloaded)} files")
        return downloaded

    async def download_filings_async(
        self,
        ticker: str,
        filing_types: list[str] = ["10-K", "10-Q", "8-K"],
        limit: int = 10,
        after: str = "2021-01-01",
        before: Optional[str] = None
    ) -> list[Path]:
        """
        Async version of download_filings with rate limiting.
        
        Note: The underlying sec-edgar-downloader is synchronous,
        so this runs in a thread pool but respects rate limits.
        """
        loop = asyncio.get_event_loop()
        
        # Run the synchronous download in a thread pool
        return await loop.run_in_executor(
            None,
            lambda: self.download_filings(ticker, filing_types, limit, after, before)
        )

    def download_all_companies(
        self,
        tickers: list[str],
        filing_types: list[str] = ["10-K", "10-Q", "8-K"],
        limit: int = 10,
        after: str = "2021-01-01",
        delay_between_companies: float = 2.0
    ) -> dict[str, list[Path]]:
        """
        Download filings for multiple companies with extra delays.
        
        Args:
            tickers: List of ticker symbols
            filing_types: List of filing types to download
            limit: Maximum filings per type per company
            after: Only filings after this date
            delay_between_companies: Extra delay between companies (seconds)
            
        Returns:
            Dict mapping ticker -> list of downloaded file paths
        """
        results = {}
        
        for i, ticker in enumerate(tickers):
            logger.info(f"\n{'='*50}")
            logger.info(f"Processing {ticker} ({i+1}/{len(tickers)})")
            logger.info(f"{'='*50}")
            
            try:
                files = self.download_filings(
                    ticker=ticker,
                    filing_types=filing_types,
                    limit=limit,
                    after=after
                )
                results[ticker] = files
                
            except Exception as e:
                logger.error(f"Failed to process {ticker}: {e}")
                results[ticker] = []
            
            # Extra delay between companies to be safe
            if i < len(tickers) - 1:
                logger.info(f"Waiting {delay_between_companies}s before next company...")
                time.sleep(delay_between_companies)
        
        # Summary
        total_files = sum(len(files) for files in results.values())
        successful = sum(1 for files in results.values() if files)
        logger.info(f"\n{'='*50}")
        logger.info(f"DOWNLOAD COMPLETE")
        logger.info(f"Companies: {successful}/{len(tickers)} successful")
        logger.info(f"Total files: {total_files}")
        logger.info(f"{'='*50}")
        
        return results

    def get_filing_path(self, ticker: str, filing_type: str) -> Optional[Path]:
        """Get the path to downloaded filings for a company."""
        library_form = FILING_TYPE_TO_LIBRARY.get(filing_type, filing_type)
        filing_dir = self.download_dir / "sec-edgar-filings" / ticker / library_form
        return filing_dir if filing_dir.exists() else None

    def list_downloaded_filings(self, ticker: Optional[str] = None) -> list[Path]:
        """List all downloaded filings, optionally filtered by ticker."""
        base_dir = self.download_dir / "sec-edgar-filings"
        
        if not base_dir.exists():
            return []
            
        if ticker:
            pattern = f"{ticker}/**/full-submission.txt"
        else:
            pattern = "**/full-submission.txt"
            
        return list(base_dir.glob(pattern))