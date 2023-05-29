import ape
import pytest

DAY_LENGTH = 24 * 60 * 60
WEEK_LENGTH = 7 * DAY_LENGTH
NATIVE = '0x0000000000000000000000000000000000000000'
ONE = 1_000_000_000_000_000_000
MAX = 2**256 - 1

@pytest.fixture
def deployer(accounts):
    return accounts[0]

@pytest.fixture
def treasury(accounts):
    return accounts[1]

@pytest.fixture
def alice(accounts):
    return accounts[2]

@pytest.fixture
def bob(accounts):
    return accounts[3]

@pytest.fixture
def token(project, deployer):
    return project.Token.deploy(sender=deployer)

@pytest.fixture
def staking(project, deployer, token):
    return project.MockStaking.deploy(token, sender=deployer)

@pytest.fixture
def pol(project, deployer, token):
    return project.POL.deploy(token, sender=deployer)

@pytest.fixture
def bootstrap(project, chain, deployer, treasury, pol, token, staking):
    bootstrap = project.Bootstrap.deploy(token, staking, treasury, pol, sender=deployer)
    token.set_minter(bootstrap, sender=deployer)
    ts = chain.pending_timestamp
    bootstrap.set_whitelist_period(ts, ts + WEEK_LENGTH, sender=deployer)
    bootstrap.set_incentive_period(ts, ts + WEEK_LENGTH, sender=deployer)
    bootstrap.set_deposit_period(ts, ts + WEEK_LENGTH, sender=deployer)
    bootstrap.set_vote_period(ts, ts + WEEK_LENGTH, sender=deployer)
    bootstrap.set_lock_end(ts + WEEK_LENGTH, sender=deployer)
    return bootstrap

@pytest.fixture
def pool(project, deployer):
    return project.MockPool.deploy(sender=deployer)

@pytest.fixture
def shutdown(chain, project, deployer, treasury, alice, token, staking, pol, bootstrap, pool):
    shutdown = project.Shutdown.deploy(token, bootstrap, pol, sender=deployer)
    shutdown.set_pool(pool, sender=deployer)
    pol.approve(NATIVE, shutdown, MAX, sender=deployer)

    # create debt of 10 yETH
    alice.transfer(bootstrap, 10 * ONE)
    bootstrap.split(sender=deployer) # sends 9 ETH to treasury, 1 ETH to pol

    # treasury uses 9 ETH to buy LSDs, deposit into pool and repay 9 yETH of debt
    token.set_minter(treasury, sender=deployer) # we wouldnt do this in reality
    token.mint(treasury, 9 * ONE, sender=treasury)
    token.set_minter(treasury, False, sender=deployer)
    token.approve(bootstrap, 9 * ONE, sender=treasury)
    bootstrap.repay(9 * ONE, sender=treasury)
    assert bootstrap.debt() == ONE # only POL debt remains

    # claim st-yETH and withdraw yETH
    chain.pending_timestamp += WEEK_LENGTH
    bootstrap.claim(ONE, sender=alice)
    staking.withdraw(ONE, sender=alice)
    assert token.balanceOf(alice) == ONE
    token.approve(shutdown, MAX, sender=alice)

    return shutdown

def test_not_killed(alice, shutdown):
    with ape.reverts():
        shutdown.redeem(ONE, sender=alice)

def test_kill_pool(deployer, alice, token, bootstrap, pool, shutdown):
    # kill pool, activating shutdown module
    pool.set_killed(True, sender=deployer)
    
    # redemption
    pre = alice.balance
    tx = shutdown.redeem(ONE, sender=alice)
    assert bootstrap.debt() == 0
    assert token.balanceOf(alice) == 0
    assert token.balanceOf(shutdown) == 0
    assert token.balanceOf(bootstrap) == 0
    assert alice.balance - pre + tx.total_fees_paid == ONE

def test_kill_pol(deployer, alice, token, bootstrap, pol, shutdown):
    # kill POL, activating shutdown module
    pol.kill(sender=deployer)

    # redemption
    pre = alice.balance
    tx = shutdown.redeem(ONE, sender=alice)
    assert bootstrap.debt() == 0
    assert token.balanceOf(alice) == 0
    assert token.balanceOf(shutdown) == 0
    assert token.balanceOf(bootstrap) == 0
    assert alice.balance - pre + tx.total_fees_paid == ONE
