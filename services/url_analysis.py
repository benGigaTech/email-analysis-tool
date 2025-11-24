import re
from typing import List

# Basic URL regex – good enough for most mail content
URL_REGEX = re.compile(
    r"""(?i)\b((?:https?://|www\.)[^\s<>"]+)"""
)


def extract_urls(text: str) -> List[str]:
    if not text:
        return []
    urls = URL_REGEX.findall(text)
    # Normalize a bit: strip trailing punctuation
    cleaned = []
    for u in urls:
        cleaned.append(u.rstrip(').,;\'"'))
    # De-duplicate while preserving order
    seen = set()
    result = []
    for u in cleaned:
        if u not in seen:
            seen.add(u)
            result.append(u)
    return result


def analyze_url_reputation(urls: List[str]) -> List[str]:
    """
    Analyze a list of URLs for static reputation signals.
    Returns a list of warning strings (e.g. "IP address as hostname", "Suspicious TLD .xyz").
    """
    warnings = []
    
    # Common suspicious TLDs often used for abuse
    SUSPICIOUS_TLDS = {
        ".xyz", ".top", ".download", ".review", ".country", ".stream", 
        ".gdn", ".mom", ".pro", ".men", ".click", ".link", ".zip", ".mov"
    }
    
    # Regex to detect IP addresses (IPv4)
    IP_REGEX = re.compile(r"^(?:https?://|www\.)(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})")

    for u in urls:
        lower_u = u.lower()
        
        # Check 1: IP Address
        ip_match = IP_REGEX.search(lower_u)
        if ip_match:
            warnings.append(f"URL contains IP address: {ip_match.group(1)}")
        
        # Check 2: Suspicious TLDs
        # Extract domain part roughly
        try:
            # Remove protocol
            domain_part = lower_u.replace("https://", "").replace("http://", "").split("/")[0]
            # Check TLD
            for tld in SUSPICIOUS_TLDS:
                if domain_part.endswith(tld):
                    warnings.append(f"URL uses suspicious TLD: {tld} ({domain_part})")
        except Exception:
            pass

    return list(set(warnings))  # Deduplicate warnings