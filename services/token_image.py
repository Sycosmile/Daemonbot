"""
services/token_image.py — Best-effort token image resolution.
Daemonbot — MR SYCO (@Sycosmile)

Three tiers, in order:
  1. DexScreener's own `info.imageUrl`/`header` — only present for tokens
     that paid for DexScreener's "Enhanced Token Info" product. Most tokens
     don't have this.
  2. pump.fun's own image (Solana only) — for tokens still on/near the
     bonding curve.
  3. Trust Wallet's public token-logo repo on GitHub — a huge, free,
     community-maintained set of logos keyed by contract address, covering
     most ERC-20/BEP-20/etc. tokens regardless of DexScreener payment
     status. This is what actually rescues the common case: an
     established, real token that just never paid DexScreener for the
     Enhanced Info add-on.
"""

import httpx
from Crypto.Hash import keccak

TRUSTWALLET_BASE = "https://raw.githubusercontent.com/trustwallet/assets/master/blockchains"

# DexScreener chainId -> Trust Wallet's blockchain folder name (they don't
# always match — most notably BSC is "smartchain" and Avalanche C-Chain is
# "avalanchec").
_TW_CHAIN_MAP = {
    "ethereum": "ethereum",
    "bsc": "smartchain",
    "base": "base",
    "arbitrum": "arbitrum",
    "polygon": "polygon",
    "avalanche": "avalanchec",
    "solana": "solana",
}


def _to_checksum_address(address: str) -> str:
    """EIP-55 mixed-case checksum — Trust Wallet's repo is case-sensitive
    and only recognizes the checksummed form, not all-lowercase."""
    addr = address.lower().replace("0x", "")
    digest = keccak.new(digest_bits=256, data=addr.encode()).hexdigest()
    out = "0x"
    for i, ch in enumerate(addr):
        if ch in "0123456789":
            out += ch
        else:
            out += ch.upper() if int(digest[i], 16) >= 8 else ch
    return out


async def get_trustwallet_logo(chain: str, address: str) -> str | None:
    """Returns a working Trust Wallet logo URL, or None if this chain isn't
    supported or the repo simply doesn't have this token. Does a real HEAD
    request first so callers never attach a dead image URL."""
    tw_chain = _TW_CHAIN_MAP.get(chain.lower())
    if not tw_chain:
        return None

    addr = address if tw_chain == "solana" else _to_checksum_address(address)
    url = f"{TRUSTWALLET_BASE}/{tw_chain}/assets/{addr}/logo.png"

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.head(url)
            if r.status_code == 200:
                return url
    except httpx.HTTPError:
        pass
    return None


async def resolve_token_image(pair: dict, ca: str) -> str | None:
    """Full 3-tier resolution given a DexScreener pair dict + the token's
    contract address. Use this everywhere a token image is needed so every
    command benefits from the same fallback chain."""
    info = pair.get("info", {}) or {}
    img = info.get("imageUrl") or info.get("header")
    if img:
        return img

    chain = pair.get("chainId", "").lower()

    if chain == "solana":
        from services.pumpfun import fetch_pumpfun_coin
        pf = await fetch_pumpfun_coin(ca)
        if pf and pf.get("image_uri"):
            return pf["image_uri"]

    return await get_trustwallet_logo(chain, ca)
