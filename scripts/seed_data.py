# scripts/seed_data.py
"""
Reference data for seeding: tokens and protocol contracts.

Imported by seed_dev_environment.py and by anyone else who needs the canonical
list of tokens/contracts the system knows about.

Single source of truth — don't duplicate this data anywhere else.
"""
from __future__ import annotations

CHAIN_ID_MAINNET = 1
CHAIN_ID_BASE_SEPOLIA = 84532

# -----------------------------------------------------------------
# Tokens (ERC-20s the indexer watches)
# -----------------------------------------------------------------

USDC = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
USDT = "0xdac17f958d2ee523a2206206994597c13d831ec7"
WEETH = "0xcd5fe23c85820f7b72d0926fc9b05b43e359b7ee"
REFLOW = "0xde41931eb4742187f015315a7388d3b4e8a7fb1d"

TOKENS = [
    {
        "chain_id": CHAIN_ID_MAINNET,
        "address": USDC,
        "symbol": "USDC",
        "name": "USD Coin",
        "decimals": 6,
        "color": "#2775CA",
        "is_active": True,
    },
    {
        "chain_id": CHAIN_ID_MAINNET,
        "address": USDT,
        "symbol": "USDT",
        "name": "Tether USD",
        "decimals": 6,
        "color": "#26A17B",
        "is_active": True,
    },
    {
        "chain_id": CHAIN_ID_MAINNET,
        "address": WEETH,
        "symbol": "weETH",
        "name": "Wrapped eETH",
        "decimals": 18,
        "color": "#FF8C42",
        "is_active": True,
    },
    {
        "chain_id": CHAIN_ID_BASE_SEPOLIA,
        "address": REFLOW,
        "symbol": "REFLOW",
        "name": "Reflow Token",
        "decimals": 18,
        "color": "#6E56CF",
        "is_active": True,
    },
]


# -----------------------------------------------------------------
# Protocol contracts (counterparties the indexer filters by)
# -----------------------------------------------------------------

# Aave V3 markets
AAVE_V3_AUSDC = "0x98c23e9d8f34fea42323f67ee2d123f1fbc0300a"
AAVE_V3_AUSDT = "0x23878914efe38d27c4d67ab83ed1b93a74d4086a"
AAVE_V3_AWETH = "0x4d5f47fa6a74757f35c14fd3a6ef8e3c9bc514e8"

# Aave V2 markets
AAVE_V2_AUSDC = "0xbcca60bb61934080951369a648fb03df4f96263c"
AAVE_V2_AUSDT = "0x3ed3b47dd13ec9a98b44e6204a523e766b225811"

# Compound V3
COMPOUND_V3_CUSDC = "0xc3d688b66703497daa19211eedff47f25384cdc3"
COMPOUND_V3_CWETH = "0xa17581a9e3356d9a858b789d68b4d866e593ae94"

# Uniswap V3 pools
UNI_V3_USDC_WETH_005 = "0x88e6a0c2ddd26feeb64f039a2c412e6ec38fec0a"
UNI_V3_USDC_WETH_03 = "0x8ad599c3a0ff1de082011efddc58f1908eb6e6d8"
UNI_V3_WBTC_WETH_005 = "0x4585fe77225b41b697c938b018e2ac67ac5a20c0"

# Uniswap V2 pools
UNI_V2_USDC_WETH = "0xb4e16d0168e52d35cacd2c6185b44281ec28c9dc"
UNI_V2_USDT_WETH = "0x0d4a11d5eeaac28ec3f61d100daf4d40471f1852"

# Lido
LIDO_STETH = "0xae7ab96520de3a18e5e111b5eaab095312d7fe84"
LIDO_WSTETH = "0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0"

# Rocket Pool
ROCKET_RETH = "0xae78736cd615f374d3085123a210448e74fc6393"

# EigenLayer
EIGEN_STRATEGY_MANAGER = "0x858646372cc42e1a627fce94aa7a7033e7cf075a"

# ether.fi
ETHERFI_EETH = "0x35fa164735182de50811e8e2e824cfb9b6118ac2"
ETHERFI_WEETH = "0xcd5fe23c85820f7b72d0926fc9b05b43e359b7ee"

# Pendle
PENDLE_WEETH_MARKET = "0x011eb2db38cccd28d844ee0ed812739ddc1bfb6e"

# Curve
CURVE_3POOL = "0xbebc44782c7db0a1a60cb6fe97d0b483032ff1c7"
CURVE_STETH_ETH = "0xdc24316b9ae028f1497c275eb9192a3ea0f67022"

CONTRACTS = [
    # Aave V3
    {"chain_id": CHAIN_ID_MAINNET, "address": AAVE_V3_AUSDC, "protocol_slug": "aave-v3", "protocol_name": "Aave V3", "protocol_color": "#B6509E", "label": "aUSDC"},
    {"chain_id": CHAIN_ID_MAINNET, "address": AAVE_V3_AUSDT, "protocol_slug": "aave-v3", "protocol_name": "Aave V3", "protocol_color": "#B6509E", "label": "aUSDT"},
    {"chain_id": CHAIN_ID_MAINNET, "address": AAVE_V3_AWETH, "protocol_slug": "aave-v3", "protocol_name": "Aave V3", "protocol_color": "#B6509E", "label": "aWETH"},

    # Aave V2
    {"chain_id": CHAIN_ID_MAINNET, "address": AAVE_V2_AUSDC, "protocol_slug": "aave-v2", "protocol_name": "Aave V2", "protocol_color": "#B6509E", "label": "aUSDC"},
    {"chain_id": CHAIN_ID_MAINNET, "address": AAVE_V2_AUSDT, "protocol_slug": "aave-v2", "protocol_name": "Aave V2", "protocol_color": "#B6509E", "label": "aUSDT"},

    # Compound V3
    {"chain_id": CHAIN_ID_MAINNET, "address": COMPOUND_V3_CUSDC, "protocol_slug": "compound-v3", "protocol_name": "Compound V3", "protocol_color": "#00D395", "label": "cUSDCv3"},
    {"chain_id": CHAIN_ID_MAINNET, "address": COMPOUND_V3_CWETH, "protocol_slug": "compound-v3", "protocol_name": "Compound V3", "protocol_color": "#00D395", "label": "cWETHv3"},

    # Uniswap V3
    {"chain_id": CHAIN_ID_MAINNET, "address": UNI_V3_USDC_WETH_005, "protocol_slug": "uniswap-v3", "protocol_name": "Uniswap V3", "protocol_color": "#FF007A", "label": "USDC-WETH 0.05%"},
    {"chain_id": CHAIN_ID_MAINNET, "address": UNI_V3_USDC_WETH_03, "protocol_slug": "uniswap-v3", "protocol_name": "Uniswap V3", "protocol_color": "#FF007A", "label": "USDC-WETH 0.3%"},
    {"chain_id": CHAIN_ID_MAINNET, "address": UNI_V3_WBTC_WETH_005, "protocol_slug": "uniswap-v3", "protocol_name": "Uniswap V3", "protocol_color": "#FF007A", "label": "WBTC-WETH 0.05%"},

    # Uniswap V2
    {"chain_id": CHAIN_ID_MAINNET, "address": UNI_V2_USDC_WETH, "protocol_slug": "uniswap-v2", "protocol_name": "Uniswap V2", "protocol_color": "#FF007A", "label": "USDC-WETH Pool"},
    {"chain_id": CHAIN_ID_MAINNET, "address": UNI_V2_USDT_WETH, "protocol_slug": "uniswap-v2", "protocol_name": "Uniswap V2", "protocol_color": "#FF007A", "label": "USDT-WETH Pool"},

    # Lido
    {"chain_id": CHAIN_ID_MAINNET, "address": LIDO_STETH, "protocol_slug": "lido", "protocol_name": "Lido", "protocol_color": "#00A3FF", "label": "stETH"},
    {"chain_id": CHAIN_ID_MAINNET, "address": LIDO_WSTETH, "protocol_slug": "lido", "protocol_name": "Lido", "protocol_color": "#00A3FF", "label": "wstETH"},

    # Rocket Pool
    {"chain_id": CHAIN_ID_MAINNET, "address": ROCKET_RETH, "protocol_slug": "rocket-pool", "protocol_name": "Rocket Pool", "protocol_color": "#FF7B4F", "label": "rETH"},

    # EigenLayer
    {"chain_id": CHAIN_ID_MAINNET, "address": EIGEN_STRATEGY_MANAGER, "protocol_slug": "eigenlayer", "protocol_name": "EigenLayer", "protocol_color": "#1A0C6D", "label": "StrategyManager"},

    # ether.fi
    {"chain_id": CHAIN_ID_MAINNET, "address": ETHERFI_EETH, "protocol_slug": "etherfi", "protocol_name": "ether.fi", "protocol_color": "#A8E0FF", "label": "eETH"},
    {"chain_id": CHAIN_ID_MAINNET, "address": ETHERFI_WEETH, "protocol_slug": "etherfi", "protocol_name": "ether.fi", "protocol_color": "#A8E0FF", "label": "weETH"},

    # Pendle
    {"chain_id": CHAIN_ID_MAINNET, "address": PENDLE_WEETH_MARKET, "protocol_slug": "pendle", "protocol_name": "Pendle", "protocol_color": "#F5B301", "label": "weETH Market"},

    # Curve
    {"chain_id": CHAIN_ID_MAINNET, "address": CURVE_3POOL, "protocol_slug": "curve", "protocol_name": "Curve", "protocol_color": "#FFD800", "label": "3pool"},
    {"chain_id": CHAIN_ID_MAINNET, "address": CURVE_STETH_ETH, "protocol_slug": "curve", "protocol_name": "Curve", "protocol_color": "#FFD800", "label": "stETH-ETH Pool"},
]