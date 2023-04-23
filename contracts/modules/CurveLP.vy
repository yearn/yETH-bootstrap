# @version 0.3.7
"""
@title Curve LP Module
@author 0xkorin, Yearn Finance
@license Copyright (c) Yearn Finance, 2023 - all rights reserved
"""

from vyper.interfaces import ERC20

interface POL:
    def send_native(_receiver: address, _amount: uint256): nonpayable
    def mint(_amount: uint256): nonpayable
    def burn(_amount: uint256): nonpayable

# https://github.com/curvefi/curve-factory/blob/master/contracts/implementations/plain-2/Plain2ETHEMA.vy
interface CurvePool:
    def add_liquidity(_amounts: uint256[2], _min_mint_amount: uint256, _receiver: address): payable
    def remove_liquidity(_burn_amount: uint256, _min_amounts: uint256[2], _receiver: address) -> uint256[2]: nonpayable
    def remove_liquidity_imbalance(_amounts: uint256[2], _max_burn_amount: uint256, _receiver: address) -> uint256: nonpayable

# https://github.com/convex-eth/platform/blob/main/contracts/contracts/Booster.sol
interface Convex:
    def deposit(_pid: uint256, _amount: uint256, _stake: bool) -> bool: nonpayable

token: public(immutable(address))
pol: public(immutable(address))
management: public(address)
pool: public(address)
convex: public(address)

NATIVE: constant(address) = 0x0000000000000000000000000000000000000001
MINT: constant(address)   = 0x0000000000000000000000000000000000000002
BURN: constant(address)   = 0x0000000000000000000000000000000000000003

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
        raw_call(pol, b"", value=_amount)
    else:
        assert ERC20(_token).transfer(pol, _amount, default_return_value=True)

@external
def approve_pool(_amount: uint256):
    assert msg.sender == self.management
    assert ERC20(token).approve(self.pool, _amount, default_return_value=True)

@external
def add_liquidity(_amounts: uint256[2], _min_lp: uint256):
    assert msg.sender == self.management
    CurvePool(self.pool).add_liquidity(_amounts, _min_lp, pol)

@external
def remove_liquidity(_lp_amount: uint256, _min_amounts: uint256[2]):
    assert msg.sender == self.management
    CurvePool(self.pool).remove_liquidity(_lp_amount, _min_amounts, pol)

@external
def remove_liquidity_imbalance(_amounts: uint256[2], _max_lp: uint256):
    assert msg.sender == self.management
    CurvePool(self.pool).remove_liquidity_imbalance(_amounts, _max_lp, pol)

@external
def approve_convex(_amount: uint256):
    assert msg.sender == self.management
    assert ERC20(self.pool).approve(self.convex, _amount, default_return_value=True)

@external
def set_management(_management: address):
    assert msg.sender == self.management
    self.management = _management

@external
def set_pool(_pool: address):
    assert msg.sender == self.management
    self.pool = _pool

@external
def set_convex(_convex: address):
    assert msg.sender == self.management
    self.convex = _convex
