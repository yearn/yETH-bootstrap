# @version 0.3.7
"""
@title Curve LP Module
@author 0xkorin, Yearn Finance
@license Copyright (c) Yearn Finance, 2023 - all rights reserved
"""

from vyper.interfaces import ERC20

interface POL:
    def receive_native(): payable
    def send_native(_receiver: address, _amount: uint256): nonpayable
    def mint(_amount: uint256): nonpayable
    def burn(_amount: uint256): nonpayable

# https://github.com/curvefi/curve-factory/blob/master/contracts/implementations/plain-2/Plain2ETHEMA.vy
interface CurvePool:
    def add_liquidity(_amounts: uint256[2], _min_mint_amount: uint256, _receiver: address): payable
    def remove_liquidity(_burn_amount: uint256, _min_amounts: uint256[2], _receiver: address) -> uint256[2]: nonpayable
    def remove_liquidity_imbalance(_amounts: uint256[2], _max_burn_amount: uint256, _receiver: address) -> uint256: nonpayable

# https://github.com/curvefi/curve-factory/blob/master/contracts/LiquidityGauge.vy
interface CurveGauge:
    def set_rewards_receiver(_receiver: address): nonpayable
    def deposit(_value: uint256): nonpayable
    def withdraw(_value: uint256): nonpayable

# https://github.com/convex-eth/platform/blob/main/contracts/contracts/Booster.sol
interface ConvexBooster:
    def deposit(_pid: uint256, _amount: uint256, _stake: bool) -> bool: nonpayable
    def withdraw(_pid: uint256, _amount: uint256) -> bool: nonpayable

# https://github.com/convex-eth/platform/blob/main/contracts/contracts/BaseRewardPool.sol
interface ConvexRewards:
    def stake(_amount: uint256): nonpayable
    def withdraw(_amount: uint256, _claim: bool): nonpayable
    def withdrawAndUnwrap(_amount: uint256, _claim: bool): nonpayable

# https://github.com/yearn/yearn-vaults/blob/master/contracts/Vault.vy
interface YVault:
    def deposit(_amount: uint256): nonpayable
    def withdraw(_shares: uint256, _recipient: address, _max_loss: uint256): nonpayable

token: public(immutable(address))
pol: public(immutable(address))
management: public(address)
pending_management: public(address)
pool: public(address)
gauge: public(address)
convex_booster: public(address)
convex_pool_id: public(uint256)
convex_token: public(address)
convex_rewards: public(address)
yvault: public(address)

NATIVE: constant(address) = 0x0000000000000000000000000000000000000000
MINT: constant(address)   = 0x0000000000000000000000000000000000000001
BURN: constant(address)   = 0x0000000000000000000000000000000000000002

@external
def __init__(_token: address, _pol: address):
    token = _token
    pol = _pol
    self.management = msg.sender

@external
@payable
def __default__():
    pass

@external
def from_pol(_token: address, _amount: uint256):
    assert msg.sender == self.management
    if _token == NATIVE:
        POL(pol).send_native(self, _amount)
    elif _token == MINT:
        POL(pol).mint(_amount)
    elif _token == BURN:
        POL(pol).burn(_amount)
    else:
        assert ERC20(_token).transferFrom(pol, self, _amount, default_return_value=True)

@external
def to_pol(_token: address, _amount: uint256):
    assert msg.sender == self.management
    if _token == NATIVE:
        POL(pol).receive_native(value=_amount)
    else:
        assert ERC20(_token).transfer(pol, _amount, default_return_value=True)

@external
def set_management(_management: address):
    assert msg.sender == self.management
    self.pending_management = _management

@external
def accept_management():
    assert msg.sender == self.pending_management
    self.pending_management = empty(address)
    self.management = msg.sender

# CURVE POOL FUNCTIONS

@external
def set_pool(_pool: address):
    assert msg.sender == self.management
    self.pool = _pool

@external
def approve_pool(_amount: uint256):
    assert msg.sender == self.management
    assert ERC20(token).approve(self.pool, _amount, default_return_value=True)

@external
def add_liquidity(_amounts: uint256[2], _min_lp: uint256):
    assert msg.sender == self.management
    CurvePool(self.pool).add_liquidity(_amounts, _min_lp, pol, value=_amounts[0])

@external
def remove_liquidity(_lp_amount: uint256, _min_amounts: uint256[2]):
    assert msg.sender == self.management
    CurvePool(self.pool).remove_liquidity(_lp_amount, _min_amounts, pol)

@external
def remove_liquidity_imbalance(_amounts: uint256[2], _max_lp: uint256):
    assert msg.sender == self.management
    CurvePool(self.pool).remove_liquidity_imbalance(_amounts, _max_lp, pol)

# GAUGE FUNCTIONS

@external
def set_gauge(_gauge: address):
    assert msg.sender == self.management
    self.gauge = _gauge

@external
def approve_gauge(_amount: uint256):
    assert msg.sender == self.management
    assert self.gauge != empty(address)
    assert ERC20(self.pool).approve(self.gauge, _amount, default_return_value=True)

@external
def gauge_rewards_receiver():
    assert msg.sender == self.management
    CurveGauge(self.gauge).set_rewards_receiver(pol)

@external
def deposit_gauge(_amount: uint256):
    assert msg.sender == self.management
    CurveGauge(self.gauge).deposit(_amount)

@external
def withdraw_gauge(_amount: uint256):
    assert msg.sender == self.management
    CurveGauge(self.gauge).withdraw(_amount)
    
# CONVEX FUNCTIONS

@external
def set_convex_booster(_booster: address):
    assert msg.sender == self.management
    self.convex_booster = _booster

@external
def set_convex_pool_id(_pool_id: uint256):
    assert msg.sender == self.management
    self.convex_pool_id = _pool_id

@external
def set_convex_token(_token: address):
    assert msg.sender == self.management
    self.convex_token = _token

@external
def set_convex_rewards(_rewards: address):
    assert msg.sender == self.management
    self.convex_rewards = _rewards

@external
def approve_convex_booster(_amount: uint256):
    assert msg.sender == self.management
    assert self.convex_booster != empty(address)
    assert ERC20(self.pool).approve(self.convex_booster, _amount, default_return_value=True)

@external
def deposit_convex_booster(_amount: uint256):
    assert msg.sender == self.management
    assert self.convex_pool_id != 0
    ConvexBooster(self.convex_booster).deposit(self.convex_pool_id, _amount, True)

@external
def withdraw_convex_booster(_amount: uint256):
    assert msg.sender == self.management
    assert self.convex_pool_id != 0
    ConvexBooster(self.convex_booster).withdraw(self.convex_pool_id, _amount)

@external
def approve_convex_rewards(_amount: uint256):
    assert msg.sender == self.management
    assert self.convex_rewards != empty(address)
    assert ERC20(self.convex_token).approve(self.convex_rewards, _amount, default_return_value=True)

@external
def deposit_convex_rewards(_amount: uint256):
    assert msg.sender == self.management
    ConvexRewards(self.convex_rewards).stake(_amount)

@external
def withdraw_convex_rewards(_amount: uint256, _unwrap: bool):
    assert msg.sender == self.management
    if _unwrap:
        ConvexRewards(self.convex_rewards).withdrawAndUnwrap(_amount, True)
    else:
        ConvexRewards(self.convex_rewards).withdraw(_amount, True)

# YVAULT FUNCTIONS

@external
def set_yvault(_yvault: address):
    assert msg.sender == self.management
    self.yvault = _yvault

@external
def approve_yvault(_amount: uint256):
    assert msg.sender == self.management
    assert self.yvault != empty(address)
    assert ERC20(self.pool).approve(self.yvault, _amount, default_return_value=True)

@external
def deposit_yvault(_amount: uint256):
    assert msg.sender == self.management
    YVault(self.yvault).deposit(_amount)

@external
def withdraw_yvault(_amount: uint256, _max_loss: uint256):
    assert msg.sender == self.management
    YVault(self.yvault).withdraw(_amount, self, _max_loss)
