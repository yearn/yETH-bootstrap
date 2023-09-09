import ape
from ape import Contract
import pytest

ZERO_ADDRESS = '0x0000000000000000000000000000000000000000'
NATIVE = '0x0000000000000000000000000000000000000000'
MINT   = '0x0000000000000000000000000000000000000001'
BURN   = '0x0000000000000000000000000000000000000002'
ONE    = 1_000_000_000_000_000_000
MAX    = 2**256 - 1

WETH = '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2'
FACTORY = '0xB9fC157394Af804a3578134A6585C0dc9cc990d4'
GAUGE_CONTROLLER = '0x2F50D538606Fa9EDD2B11E2446BEb18C9D5846bB'
GAUGE_CONTROLLER_ADMIN = '0x40907540d8a6C65c637785e8f8B742ae6b0b9968'
CONVEX_POOL_MANAGER = '0xc461E1CE3795Ee30bA2EC59843d5fAe14d5782D5'
CONVEX_BOOSTER = '0xF403C135812408BFbE8713b5A23a04b3D48AAE31'
YEARN_FACTORY = '0x21b1FC8A52f179757bf555346130bF27c0C2A17A'

@pytest.fixture
def deployer(accounts):
    return accounts[0]

@pytest.fixture
def operator(accounts):
    return accounts[1]

@pytest.fixture
def alice(accounts):
    return accounts[2]

@pytest.fixture
def token(project, deployer):
    return project.Token.deploy(sender=deployer)

@pytest.fixture
def weth():
    return Contract(WETH)

@pytest.fixture
def pol(project, alice, deployer, token):
    pol = project.POL.deploy(token, sender=deployer)
    token.set_minter(pol, sender=deployer)
    alice.transfer(pol, ONE)
    return pol

@pytest.fixture
def curve_module(project, deployer, operator, token, pol):
    curve_module = project.CurveLP.deploy(token, pol, WETH, sender=deployer)
    curve_module.set_operator(operator, sender=deployer)
    curve_module.accept_operator(sender=operator)
    pol.approve(MINT, curve_module, MAX, sender=deployer)
    pol.approve(NATIVE, curve_module, MAX, sender=deployer)
    pol.approve(token, curve_module, MAX, sender=deployer)
    return curve_module

@pytest.fixture
def curve_pool(project, deployer, operator, token, pol, curve_module):
    factory = Contract(FACTORY)
    factory.deploy_plain_pool('yETH', 'yETH', [WETH, token, ZERO_ADDRESS, ZERO_ADDRESS], 100, 4000000, 1, 4, sender=deployer)
    curve_pool = factory.find_pool_for_coins(WETH, token)
    curve_module.set_pool(curve_pool, sender=deployer)
    curve_module.approve_pool_yeth(MAX, sender=operator)
    curve_module.approve_pool_weth(MAX, sender=operator)
    return project.MockToken.at(curve_pool)

@pytest.fixture
def gauge(project, accounts, deployer, operator, curve_pool, curve_module):
    factory = Contract(FACTORY)
    factory.deploy_gauge(curve_pool, sender=deployer)
    gauge = factory.get_gauge(curve_pool, sender=deployer)
    controller = Contract(GAUGE_CONTROLLER)
    controller.add_gauge(gauge, 0, 1_000_000 * ONE, sender=accounts[GAUGE_CONTROLLER_ADMIN])
    curve_module.set_gauge(gauge, sender=deployer)
    curve_module.gauge_rewards_receiver(sender=operator)
    curve_module.approve_gauge(MAX, sender=operator)
    return project.MockToken.at(gauge)

@pytest.fixture
def convex_booster(deployer, operator, curve_pool, curve_module):
    booster = Contract(CONVEX_BOOSTER)
    curve_module.set_convex_booster(booster, sender=deployer)
    curve_module.approve_convex_booster(MAX, sender=operator)
    return booster

@pytest.fixture
def convex_pool_id(deployer, curve_module, gauge, convex_booster):
    id = convex_booster.poolLength()
    manager = Contract(CONVEX_POOL_MANAGER)
    manager.addPool(gauge, sender=deployer)
    curve_module.set_convex_pool_id(id, sender=deployer)
    return id

@pytest.fixture
def convex_token(project, deployer, curve_module, convex_booster, convex_pool_id):
    token = convex_booster.poolInfo(convex_pool_id).token
    curve_module.set_convex_token(token, sender=deployer)
    return project.MockToken.at(token)

@pytest.fixture
def convex_rewards(project, deployer, operator, curve_module, convex_booster, convex_pool_id, convex_token):
    rewards = convex_booster.poolInfo(convex_pool_id).crvRewards
    curve_module.set_convex_rewards(rewards, sender=deployer)
    curve_module.approve_convex_rewards(MAX, sender=operator)
    return project.MockToken.at(rewards)

@pytest.fixture
def yvault(project, deployer, operator, curve_module, gauge, convex_rewards):
    factory = Contract(YEARN_FACTORY)
    idx = factory.numVaults()
    factory.createNewVaultsAndStrategies(gauge, sender=deployer)
    vault = factory.deployedVaults(idx)
    curve_module.set_yvault(vault, sender=deployer)
    curve_module.approve_yvault(MAX, sender=operator)
    return project.MockToken.at(vault)

def test_from_pol_native(project, operator, curve_module):
    assert project.provider.get_balance(curve_module.address) == 0
    curve_module.from_pol(NATIVE, ONE, sender=operator)
    assert project.provider.get_balance(curve_module.address) == ONE

def test_from_pol_mint(operator, token, pol, curve_module):
    assert token.balanceOf(pol) == 0
    curve_module.from_pol(MINT, ONE, sender=operator)
    assert token.balanceOf(pol) == ONE

def test_from_pol_token(operator, token, curve_module):
    curve_module.from_pol(MINT, ONE, sender=operator)
    assert token.balanceOf(curve_module) == 0
    curve_module.from_pol(token, ONE, sender=operator)
    assert token.balanceOf(curve_module) == ONE

def test_to_pol_native(project, operator, pol, curve_module):
    curve_module.from_pol(NATIVE, ONE, sender=operator)
    before = project.provider.get_balance(pol.address)
    curve_module.to_pol(NATIVE, ONE, sender=operator)
    assert project.provider.get_balance(curve_module.address) == 0
    assert project.provider.get_balance(pol.address) - before == ONE

def test_to_pol_native_max(project, operator, pol, curve_module):
    curve_module.from_pol(NATIVE, ONE, sender=operator)
    before = project.provider.get_balance(pol.address)
    curve_module.to_pol(NATIVE, MAX, sender=operator)
    assert project.provider.get_balance(curve_module.address) == 0
    assert project.provider.get_balance(pol.address) - before == ONE

def test_to_pol_token(operator, token, pol, curve_module):
    curve_module.from_pol(MINT, ONE, sender=operator)
    curve_module.from_pol(token, ONE, sender=operator)
    curve_module.to_pol(token, ONE, sender=operator)
    assert token.balanceOf(curve_module) == 0
    assert token.balanceOf(pol) == ONE

def test_to_pol_token_max(operator, token, pol, curve_module):
    curve_module.from_pol(MINT, ONE, sender=operator)
    curve_module.from_pol(token, ONE, sender=operator)
    curve_module.to_pol(token, MAX, sender=operator)
    assert token.balanceOf(curve_module) == 0
    assert token.balanceOf(pol) == ONE

def test_wrap(operator, weth, curve_module):
    curve_module.from_pol(NATIVE, ONE, sender=operator)
    curve_module.wrap(ONE, sender=operator)
    assert weth.balanceOf(curve_module) == ONE

def test_unwrap(project, operator, weth, curve_module):
    curve_module.from_pol(NATIVE, ONE, sender=operator)
    curve_module.wrap(ONE, sender=operator)
    curve_module.unwrap(ONE, sender=operator)
    assert weth.balanceOf(curve_module) == 0
    assert project.provider.get_balance(curve_module.address) == ONE

def test_add_liquidity(project, operator, token, curve_pool, curve_module):
    curve_module.from_pol(NATIVE, ONE, sender=operator)
    curve_module.from_pol(MINT, ONE, sender=operator)
    curve_module.from_pol(token, ONE, sender=operator)
    curve_module.wrap(ONE, sender=operator)
    with ape.reverts():
        curve_module.add_liquidity([ONE, ONE], 2 * ONE + 1, sender=operator)
    curve_module.add_liquidity([ONE, ONE], 2 * ONE, sender=operator)
    assert curve_pool.balanceOf(curve_module) == 2 * ONE
    assert project.provider.get_balance(curve_module.address) == 0
    assert token.balanceOf(curve_module) == 0

def test_remove_liquidity(project, operator, token, curve_pool, curve_module):
    curve_module.from_pol(NATIVE, ONE, sender=operator)
    curve_module.from_pol(MINT, ONE, sender=operator)
    curve_module.from_pol(token, ONE, sender=operator)
    curve_module.wrap(ONE, sender=operator)
    curve_module.add_liquidity([ONE, ONE], 2 * ONE, sender=operator)
    
    with ape.reverts():
        curve_module.remove_liquidity(2 * ONE, [ONE + 1, ONE], sender=operator)
    curve_module.remove_liquidity(2 * ONE, [ONE, ONE], sender=operator)
    curve_module.unwrap(ONE, sender=operator)
    assert curve_pool.balanceOf(curve_module) == 0
    assert project.provider.get_balance(curve_module.address) == ONE
    assert token.balanceOf(curve_module) == ONE

def test_remove_liquidity_imbalance(project, operator, token, curve_pool, curve_module):
    curve_module.from_pol(NATIVE, ONE, sender=operator)
    curve_module.from_pol(MINT, ONE, sender=operator)
    curve_module.from_pol(token, ONE, sender=operator)
    curve_module.wrap(ONE, sender=operator)
    curve_module.add_liquidity([ONE, ONE], 2 * ONE, sender=operator)
    
    curve_module.remove_liquidity_imbalance([2 * ONE // 100, ONE // 100], ONE, sender=operator)
    curve_module.unwrap(ONE * 2 // 100, sender=operator)
    bal = curve_pool.balanceOf(curve_module)
    assert bal > ONE * 196 // 100 and bal < ONE * 197 // 100
    assert project.provider.get_balance(curve_module.address) == ONE * 2 // 100
    assert token.balanceOf(curve_module) == ONE // 100

def test_deposit_gauge(operator, token, curve_module, gauge):
    curve_module.from_pol(NATIVE, ONE, sender=operator)
    curve_module.from_pol(MINT, ONE, sender=operator)
    curve_module.from_pol(token, ONE, sender=operator)
    curve_module.wrap(ONE, sender=operator)
    curve_module.add_liquidity([ONE, ONE], 2 * ONE, sender=operator)

    assert gauge.balanceOf(curve_module) == 0
    curve_module.deposit_gauge(2 * ONE, sender=operator)
    assert gauge.balanceOf(curve_module) == 2 * ONE

def test_withdraw_gauge(operator, token, curve_pool, curve_module, gauge):
    curve_module.from_pol(NATIVE, ONE, sender=operator)
    curve_module.from_pol(MINT, ONE, sender=operator)
    curve_module.from_pol(token, ONE, sender=operator)
    curve_module.wrap(ONE, sender=operator)
    curve_module.add_liquidity([ONE, ONE], 2 * ONE, sender=operator)
    curve_module.deposit_gauge(2 * ONE, sender=operator)

    assert curve_pool.balanceOf(curve_module) == 0
    curve_module.withdraw_gauge(2 * ONE, sender=operator)
    assert curve_pool.balanceOf(curve_module) == 2 * ONE
    assert gauge.balanceOf(curve_module) == 0

def test_deposit_convex(operator, token, curve_module, convex_token):
    curve_module.from_pol(NATIVE, ONE, sender=operator)
    curve_module.from_pol(MINT, ONE, sender=operator)
    curve_module.from_pol(token, ONE, sender=operator)
    curve_module.wrap(ONE, sender=operator)
    curve_module.add_liquidity([ONE, ONE], 2 * ONE, sender=operator)

    assert convex_token.balanceOf(curve_module) == 0
    curve_module.deposit_convex_booster(2 * ONE, False, sender=operator)
    assert convex_token.balanceOf(curve_module) == 2 * ONE

def test_deposit_stake_convex(operator, token, curve_module, convex_rewards):
    curve_module.from_pol(NATIVE, ONE, sender=operator)
    curve_module.from_pol(MINT, ONE, sender=operator)
    curve_module.from_pol(token, ONE, sender=operator)
    curve_module.wrap(ONE, sender=operator)
    curve_module.add_liquidity([ONE, ONE], 2 * ONE, sender=operator)

    assert convex_rewards.balanceOf(curve_module) == 0
    curve_module.deposit_convex_booster(2 * ONE, True, sender=operator)
    assert convex_rewards.balanceOf(curve_module) == 2 * ONE

def test_stake_convex(operator, token, curve_module, convex_rewards):
    curve_module.from_pol(NATIVE, ONE, sender=operator)
    curve_module.from_pol(MINT, ONE, sender=operator)
    curve_module.from_pol(token, ONE, sender=operator)
    curve_module.wrap(ONE, sender=operator)
    curve_module.add_liquidity([ONE, ONE], 2 * ONE, sender=operator)
    curve_module.deposit_convex_booster(2 * ONE, False, sender=operator)

    assert convex_rewards.balanceOf(curve_module) == 0
    curve_module.deposit_convex_rewards(2 * ONE, sender=operator)
    assert convex_rewards.balanceOf(curve_module) == 2 * ONE

def test_withdraw_convex(operator, token, curve_module, curve_pool, convex_token):
    curve_module.from_pol(NATIVE, ONE, sender=operator)
    curve_module.from_pol(MINT, ONE, sender=operator)
    curve_module.from_pol(token, ONE, sender=operator)
    curve_module.wrap(ONE, sender=operator)
    curve_module.add_liquidity([ONE, ONE], 2 * ONE, sender=operator)
    curve_module.deposit_convex_booster(2 * ONE, False, sender=operator)

    assert curve_pool.balanceOf(curve_module) == 0
    curve_module.withdraw_convex_booster(2 * ONE, sender=operator)
    assert curve_pool.balanceOf(curve_module) == 2 * ONE
    assert convex_token.balanceOf(curve_module) == 0

def test_unstake_convex(operator, token, curve_module, convex_token, convex_rewards):
    curve_module.from_pol(NATIVE, ONE, sender=operator)
    curve_module.from_pol(MINT, ONE, sender=operator)
    curve_module.from_pol(token, ONE, sender=operator)
    curve_module.wrap(ONE, sender=operator)
    curve_module.add_liquidity([ONE, ONE], 2 * ONE, sender=operator)
    curve_module.deposit_convex_booster(2 * ONE, False, sender=operator)
    curve_module.deposit_convex_rewards(2 * ONE, sender=operator)

    assert convex_token.balanceOf(curve_module) == 0
    curve_module.withdraw_convex_rewards(2 * ONE, False, sender=operator)
    assert convex_token.balanceOf(curve_module) == 2 * ONE
    assert convex_rewards.balanceOf(curve_module) == 0

def test_unstake_withdraw_convex(operator, token, curve_pool, curve_module, convex_rewards):
    curve_module.from_pol(NATIVE, ONE, sender=operator)
    curve_module.from_pol(MINT, ONE, sender=operator)
    curve_module.from_pol(token, ONE, sender=operator)
    curve_module.wrap(ONE, sender=operator)
    curve_module.add_liquidity([ONE, ONE], 2 * ONE, sender=operator)
    curve_module.deposit_convex_booster(2 * ONE, False, sender=operator)
    curve_module.deposit_convex_rewards(2 * ONE, sender=operator)

    assert curve_pool.balanceOf(curve_module) == 0
    curve_module.withdraw_convex_rewards(2 * ONE, True, sender=operator)
    assert curve_pool.balanceOf(curve_module) == 2 * ONE
    assert convex_rewards.balanceOf(curve_module) == 0

def test_deposit_yvault(operator, token, curve_module, yvault):
    curve_module.from_pol(NATIVE, ONE, sender=operator)
    curve_module.from_pol(MINT, ONE, sender=operator)
    curve_module.from_pol(token, ONE, sender=operator)
    curve_module.wrap(ONE, sender=operator)
    curve_module.add_liquidity([ONE, ONE], 2 * ONE, sender=operator)
    
    assert yvault.balanceOf(curve_module) == 0
    curve_module.deposit_yvault(2 * ONE, sender=operator)
    assert yvault.balanceOf(curve_module) == 2 * ONE

def test_withdraw_yvault(operator, token, curve_module, curve_pool, yvault):
    curve_module.from_pol(NATIVE, ONE, sender=operator)
    curve_module.from_pol(MINT, ONE, sender=operator)
    curve_module.from_pol(token, ONE, sender=operator)
    curve_module.wrap(ONE, sender=operator)
    curve_module.add_liquidity([ONE, ONE], 2 * ONE, sender=operator)
    curve_module.deposit_yvault(2 * ONE, sender=operator)
    
    assert curve_pool.balanceOf(curve_module) == 0
    curve_module.withdraw_yvault(2 * ONE, 0, sender=operator)
    assert curve_pool.balanceOf(curve_module) == 2 * ONE
    assert yvault.balanceOf(curve_module) == 0
