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
def alice(accounts):
    return accounts[1]

@pytest.fixture
def bob(accounts):
    return accounts[2]

@pytest.fixture
def token(project, deployer):
    return project.Token.deploy(sender=deployer)

@pytest.fixture
def staking(project, deployer, token):
    return project.MockStaking.deploy(token, sender=deployer)

@pytest.fixture
def bootstrap(project, chain, deployer, token, staking):
    bootstrap = project.Bootstrap.deploy(token, staking, sender=deployer)
    token.set_minter(bootstrap, sender=deployer)
    ts = (chain.pending_timestamp // WEEK_LENGTH + 1) * WEEK_LENGTH
    bootstrap.set_whitelist_period(ts, ts + WEEK_LENGTH, sender=deployer)
    bootstrap.set_incentive_period(ts + WEEK_LENGTH, ts + 2 * WEEK_LENGTH, sender=deployer)
    bootstrap.set_deposit_period(ts + 2 * WEEK_LENGTH, ts + 3 * WEEK_LENGTH, sender=deployer)
    bootstrap.set_vote_period(ts + 3 * WEEK_LENGTH, ts + 4 * WEEK_LENGTH, sender=deployer)
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
