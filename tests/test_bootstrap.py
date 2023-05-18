import ape
import pytest

DAY_LENGTH = 24 * 60 * 60
WEEK_LENGTH = 7 * DAY_LENGTH
ONE = 1_000_000_000_000_000_000
MAX = 2**256 - 1

@pytest.fixture
def deployer(accounts):
    return accounts[0]

@pytest.fixture
def pol(accounts):
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
def bootstrap(project, chain, deployer, pol, token, staking):
    bootstrap = project.Bootstrap.deploy(token, staking, deployer, pol, sender=deployer)
    token.set_minter(bootstrap, sender=deployer)
    ts = (chain.pending_timestamp // WEEK_LENGTH + 1) * WEEK_LENGTH
    bootstrap.set_whitelist_period(ts, ts + WEEK_LENGTH, sender=deployer)
    bootstrap.set_incentive_period(ts + WEEK_LENGTH, ts + 2 * WEEK_LENGTH, sender=deployer)
    bootstrap.set_deposit_period(ts + 2 * WEEK_LENGTH, ts + 3 * WEEK_LENGTH, sender=deployer)
    bootstrap.set_vote_period(ts + 3 * WEEK_LENGTH, ts + 4 * WEEK_LENGTH, sender=deployer)
    bootstrap.set_lock_end(ts + 5 * WEEK_LENGTH, sender=deployer)
    return bootstrap

def deploy_lsd(project, deployer):
    return project.MockToken.deploy(sender=deployer)

def test_apply_early_late(project, chain, deployer, alice, bootstrap):
    protocol = deploy_lsd(project, deployer)
    with ape.reverts(dev_message='dev: outside application period'):
        bootstrap.apply(protocol, value=ONE, sender=alice)
    
    chain.pending_timestamp += 2 * WEEK_LENGTH
    with ape.reverts(dev_message='dev: outside application period'):
        bootstrap.apply(protocol, value=ONE, sender=alice)

def test_apply_fee(project, chain, deployer, alice, bootstrap):
    protocol = deploy_lsd(project, deployer)
    chain.pending_timestamp += WEEK_LENGTH
    with ape.reverts(dev_message='dev: application fee'):
        bootstrap.apply(protocol, value=ONE - 1, sender=alice)

def test_apply(project, chain, deployer, alice, bootstrap):
    protocol = deploy_lsd(project, deployer)
    chain.pending_timestamp += WEEK_LENGTH
    assert not bootstrap.has_applied(protocol)
    assert not bootstrap.is_whitelisted(protocol)
    bootstrap.apply(protocol, value=ONE, sender=alice)
    assert bootstrap.has_applied(protocol)
    assert not bootstrap.is_whitelisted(protocol)

def test_whitelist_no_application(project, chain, deployer, bootstrap):
    protocol = deploy_lsd(project, deployer)
    chain.pending_timestamp += WEEK_LENGTH
    with ape.reverts(dev_message='dev: has not applied'):
        bootstrap.whitelist(protocol, sender=deployer)

def test_whitelist(project, chain, deployer, alice, bootstrap):
    protocol = deploy_lsd(project, deployer)
    chain.pending_timestamp += WEEK_LENGTH
    bootstrap.apply(protocol, value=ONE, sender=alice)
    assert not bootstrap.is_whitelisted(protocol)
    bootstrap.whitelist(protocol, sender=deployer)
    assert bootstrap.is_whitelisted(protocol)

def test_incentivise_early_late(project, chain, deployer, alice, bootstrap):
    protocol = deploy_lsd(project, deployer)
    incentive = project.MockToken.deploy(sender=deployer)

    chain.pending_timestamp += WEEK_LENGTH
    with ape.reverts(dev_message='dev: outside incentive period'):
        bootstrap.incentivise(protocol, incentive, ONE, sender=alice)

    chain.pending_timestamp += 2 * WEEK_LENGTH
    with ape.reverts(dev_message='dev: outside incentive period'):
        bootstrap.incentivise(protocol, incentive, ONE, sender=alice)

def test_incentivise_no_whitelist(project, chain, deployer, alice, bootstrap):
    protocol = deploy_lsd(project, deployer)
    chain.pending_timestamp += WEEK_LENGTH
    bootstrap.apply(protocol, value=ONE, sender=alice)
    
    chain.pending_timestamp += WEEK_LENGTH
    incentive = project.MockToken.deploy(sender=deployer)
    with ape.reverts(dev_message='dev: not whitelisted'):
        bootstrap.incentivise(protocol, incentive, ONE, sender=alice)

def test_incentivise(project, chain, deployer, alice, bootstrap):
    protocol = deploy_lsd(project, deployer)
    chain.pending_timestamp += WEEK_LENGTH
    bootstrap.apply(protocol, value=ONE, sender=alice)
    bootstrap.whitelist(protocol, sender=deployer)

    chain.pending_timestamp += WEEK_LENGTH
    incentive = project.MockToken.deploy(sender=deployer)
    incentive.mint(alice, ONE, sender=deployer)
    incentive.approve(bootstrap, MAX, sender=alice)

    assert bootstrap.incentives(protocol, incentive) == 0
    bootstrap.incentivise(protocol, incentive, ONE, sender=alice)
    assert bootstrap.incentives(protocol, incentive) == ONE

def test_deposit_early_late(chain, alice, bootstrap):
    with ape.reverts(dev_message='dev: outside deposit period'):
        alice.transfer(bootstrap, ONE)
    
    chain.pending_timestamp += 4 * WEEK_LENGTH
    with ape.reverts(dev_message='dev: outside deposit period'):
        alice.transfer(bootstrap, ONE)

def test_deposit(chain, alice, staking, bootstrap):
    chain.pending_timestamp += 3 * WEEK_LENGTH
    assert bootstrap.debt() == 0
    assert bootstrap.deposited() == 0
    assert bootstrap.deposits(alice) == 0
    assert staking.balanceOf(bootstrap) == 0

    alice.transfer(bootstrap, ONE)
    assert bootstrap.debt() == ONE
    assert bootstrap.deposited() == ONE
    assert bootstrap.deposits(alice) == ONE
    assert staking.balanceOf(bootstrap) == ONE

def test_deposit_fn(chain, alice, bob, bootstrap):
    chain.pending_timestamp += 3 * WEEK_LENGTH
    bootstrap.deposit(bob, value=ONE, sender=alice)
    assert bootstrap.deposits(bob) == ONE

def test_vote_early_late(project, chain, deployer, alice, bootstrap):
    protocol = deploy_lsd(project, deployer)
    
    with ape.reverts(dev_message='dev: outside vote period'):
        bootstrap.vote([protocol], [ONE], sender=alice)

    chain.pending_timestamp += 5 * WEEK_LENGTH
    with ape.reverts(dev_message='dev: outside vote period'):
        bootstrap.vote([protocol], [ONE], sender=alice)

def test_vote_no_application(project, chain, deployer, alice, bootstrap):
    protocol = deploy_lsd(project, deployer)

    chain.pending_timestamp += 3 * WEEK_LENGTH
    alice.transfer(bootstrap, ONE)

    chain.pending_timestamp += WEEK_LENGTH
    with ape.reverts(dev_message='dev: protocol not whitelisted'):
        bootstrap.vote([protocol], [ONE], sender=alice)

def test_vote_no_whitelist(project, chain, deployer, alice, bootstrap):
    protocol = deploy_lsd(project, deployer)

    chain.pending_timestamp += WEEK_LENGTH
    bootstrap.apply(protocol, value=ONE, sender=alice)

    chain.pending_timestamp += 2 * WEEK_LENGTH
    alice.transfer(bootstrap, ONE)

    chain.pending_timestamp += WEEK_LENGTH
    with ape.reverts(dev_message='dev: protocol not whitelisted'):
        bootstrap.vote([protocol], [ONE], sender=alice)

def test_vote_exceed(project, chain, deployer, alice, bootstrap):
    protocol = deploy_lsd(project, deployer)
    
    chain.pending_timestamp += WEEK_LENGTH
    bootstrap.apply(protocol, value=ONE, sender=alice)
    bootstrap.whitelist(protocol, sender=deployer)

    chain.pending_timestamp += 2 * WEEK_LENGTH
    alice.transfer(bootstrap, ONE)

    chain.pending_timestamp += WEEK_LENGTH
    with ape.reverts(dev_message='dev: too many votes'):
        bootstrap.vote([protocol], [ONE + 1], sender=alice)

def test_vote(project, chain, deployer, alice, bootstrap):
    protocol = deploy_lsd(project, deployer)
    
    chain.pending_timestamp += WEEK_LENGTH
    bootstrap.apply(protocol, value=ONE, sender=alice)
    bootstrap.whitelist(protocol, sender=deployer)

    chain.pending_timestamp += 2 * WEEK_LENGTH
    alice.transfer(bootstrap, ONE)

    chain.pending_timestamp += WEEK_LENGTH
    assert bootstrap.voted() == 0
    assert bootstrap.votes_used(alice) == 0
    assert bootstrap.votes(protocol) == 0

    bootstrap.vote([protocol], [ONE], sender=alice)
    assert bootstrap.voted() == ONE
    assert bootstrap.votes_used(alice) == ONE
    assert bootstrap.votes(protocol) == ONE

