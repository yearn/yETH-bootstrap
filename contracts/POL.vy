# @version 0.3.7
"""
@title Protocol Owned Liquidity
@author 0xkorin, Yearn Finance
@license Copyright (c) Yearn Finance, 2023 - all rights reserved
"""

from vyper.interfaces import ERC20

interface Token:
    def mint(_account: address, _amount: uint256): nonpayable
    def burn(_account: address, _amount: uint256): nonpayable

token: public(immutable(address))
management: public(address)
pending_management: public(address)
available: public(uint256)
debt: public(uint256)
native_allowance: public(HashMap[address, uint256])
mint_allowance: public(HashMap[address, uint256])
burn_allowance: public(HashMap[address, uint256])
killed: public(bool)

NATIVE: constant(address) = 0x0000000000000000000000000000000000000000
MINT: constant(address)   = 0x0000000000000000000000000000000000000001
BURN: constant(address)   = 0x0000000000000000000000000000000000000002

event Mint:
    account: indexed(address)
    amount: uint256

event Burn:
    account: indexed(address)
    amount: uint256

event Approve:
    token: indexed(address)
    spender: indexed(address)
    amount: uint256

event PendingManagement:
    management: indexed(address)

event SetManagement:
    management: indexed(address)

event Kill: pass

@external
def __init__(_token: address):
    token = _token
    self.management = msg.sender

@external
@payable
def __default__():
    self.available += msg.value
    pass

@external
@payable
def receive_native():
    # dont increase debt ceiling here
    pass

@external
def send_native(_receiver: address, _amount: uint256):
    assert _amount > 0
    self.native_allowance[msg.sender] -= _amount
    raw_call(_receiver, b"", value=_amount)

@external
def mint(_amount: uint256):
    assert _amount > 0
    assert not self.killed
    self.mint_allowance[msg.sender] -= _amount
    debt: uint256 = self.debt + _amount
    assert debt <= self.available
    self.debt = debt
    Token(token).mint(self, _amount)
    log Mint(msg.sender, _amount)

@external
def burn(_amount: uint256):
    assert _amount > 0
    self.burn_allowance[msg.sender] -= _amount
    self.debt -= _amount
    Token(token).burn(self, _amount)
    log Burn(msg.sender, _amount)

# MANAGEMENT FUNCTIONS

@external
def set_management(_management: address):
    assert msg.sender == self.management
    self.pending_management = _management
    log PendingManagement(_management)

@external
def accept_management():
    assert msg.sender == self.pending_management
    self.pending_management = empty(address)
    self.management = msg.sender
    log SetManagement(msg.sender)

@external
def approve(_token: address, _spender: address, _amount: uint256):
    self._approve(_token, _spender, _amount)

@external
def increase_allowance(_token: address, _spender: address, _amount: uint256):
    allowance: uint256 = 0
    if _token == NATIVE:
        allowance = self.native_allowance[_spender]
    elif _token == MINT:
        allowance = self.mint_allowance[_spender]
    elif _token == BURN:
        allowance = self.burn_allowance[_spender]
    else:
        allowance = ERC20(_token).allowance(self, _spender)

    self._approve(_token, _spender, allowance + _amount)

@external
def decrease_allowance(_token: address, _spender: address, _amount: uint256):
    allowance: uint256 = 0
    if _token == NATIVE:
        allowance = self.native_allowance[_spender]
    elif _token == MINT:
        allowance = self.mint_allowance[_spender]
    elif _token == BURN:
        allowance = self.burn_allowance[_spender]
    else:
        allowance = ERC20(_token).allowance(self, _spender)

    if _amount > allowance:
        allowance = 0
    else:
        allowance -= _amount
    self._approve(_token, _spender, allowance)

@internal
def _approve(_token: address, _spender: address, _amount: uint256):
    assert msg.sender == self.management
    if _token == NATIVE:
        self.native_allowance[_spender] = _amount
    elif _token == MINT:
        self.mint_allowance[_spender] = _amount
    elif _token == BURN:
        self.burn_allowance[_spender] = _amount
    else:
        ERC20(_token).approve(_spender, _amount)
    log Approve(_token, _spender, _amount)

@external
def kill():
    assert msg.sender == self.management
    self.killed = True
    log Kill()
