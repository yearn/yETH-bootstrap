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
def treasury(accounts):
    return accounts[1]

@pytest.fixture
def pol(accounts):
    return accounts[2]

@pytest.fixture
def alice(accounts):
    return accounts[3]

@pytest.fixture
def bob(accounts):
    return accounts[4]

@pytest.fixture
def token(project, deployer):
    return project.Token.deploy(sender=deployer)

@pytest.fixture
def staking(project, deployer, token):
    return project.MockStaking.deploy(token, sender=deployer)

@pytest.fixture
def bootstrap(project, chain, deployer, treasury, pol, token, staking):
    bootstrap = project.Bootstrap.deploy(token, staking, treasury, pol, sender=deployer)
    token.set_minter(bootstrap, sender=deployer)
    ts = (chain.pending_timestamp // WEEK_LENGTH + 1) * WEEK_LENGTH
    bootstrap.set_whitelist_period(ts, ts + WEEK_LENGTH, sender=deployer)
    bootstrap.set_incentive_period(ts + WEEK_LENGTH, ts + 2 * WEEK_LENGTH, sender=deployer)
    bootstrap.set_deposit_period(ts + 2 * WEEK_LENGTH, ts + 3 * WEEK_LENGTH, sender=deployer)
    bootstrap.set_lock_end(ts + 5 * WEEK_LENGTH, sender=deployer)
    bootstrap.set_vote_period(ts + 3 * WEEK_LENGTH, ts + 4 * WEEK_LENGTH, sender=deployer)
    return bootstrap

def test_apply_early_late(project, chain, deployer, alice, bootstrap):
    protocol = project.MockToken.deploy(sender=deployer)
    with ape.reverts(dev_message='dev: outside application period'):
        bootstrap.apply(protocol, value=ONE, sender=alice)
    
    chain.pending_timestamp += 2 * WEEK_LENGTH
    with ape.reverts(dev_message='dev: outside application period'):
        bootstrap.apply(protocol, value=ONE, sender=alice)

def test_apply_fee(project, chain, deployer, alice, bootstrap):
    protocol = project.MockToken.deploy(sender=deployer)
    chain.pending_timestamp += WEEK_LENGTH
    with ape.reverts(dev_message='dev: application fee'):
        bootstrap.apply(protocol, value=ONE - 1, sender=alice)

def test_apply(project, chain, deployer, alice, bootstrap):
    protocol = project.MockToken.deploy(sender=deployer)
    chain.pending_timestamp += WEEK_LENGTH
    assert not bootstrap.has_applied(protocol)
    assert not bootstrap.is_whitelisted(protocol)
    bootstrap.apply(protocol, value=ONE, sender=alice)
    assert bootstrap.has_applied(protocol)
    assert not bootstrap.is_whitelisted(protocol)

def test_apply_multiple(project, chain, deployer, alice, bootstrap):
    protocol = project.MockToken.deploy(sender=deployer)
    chain.pending_timestamp += WEEK_LENGTH
    bootstrap.apply(protocol, value=ONE, sender=alice)
    with ape.reverts(dev_message='dev: already applied'):
        bootstrap.apply(protocol, value=ONE, sender=alice)

def test_whitelist_no_application(project, chain, deployer, bootstrap):
    protocol = project.MockToken.deploy(sender=deployer)
    chain.pending_timestamp += WEEK_LENGTH
    with ape.reverts(dev_message='dev: has not applied'):
        bootstrap.whitelist(protocol, sender=deployer)

def test_whitelist_apply_multiple(project, chain, deployer, alice, bootstrap):
    protocol = project.MockToken.deploy(sender=deployer)
    chain.pending_timestamp += WEEK_LENGTH
    bootstrap.apply(protocol, value=ONE, sender=alice)
    bootstrap.whitelist(protocol, sender=deployer)
    with ape.reverts(dev_message='dev: already applied'):
        bootstrap.apply(protocol, value=ONE, sender=alice)

def test_whitelist(project, chain, deployer, alice, bootstrap):
    protocol = project.MockToken.deploy(sender=deployer)
    chain.pending_timestamp += WEEK_LENGTH
    bootstrap.apply(protocol, value=ONE, sender=alice)
    assert not bootstrap.is_whitelisted(protocol)
    bootstrap.whitelist(protocol, sender=deployer)
    assert bootstrap.is_whitelisted(protocol)

def test_incentivize_early_late(project, chain, deployer, alice, bootstrap):
    protocol = project.MockToken.deploy(sender=deployer)
    incentive = project.MockToken.deploy(sender=deployer)

    chain.pending_timestamp += WEEK_LENGTH
    with ape.reverts(dev_message='dev: outside incentive period'):
        bootstrap.incentivize(protocol, incentive, ONE, sender=alice)

    chain.pending_timestamp += 2 * WEEK_LENGTH
    with ape.reverts(dev_message='dev: outside incentive period'):
        bootstrap.incentivize(protocol, incentive, ONE, sender=alice)

def test_incentivize_no_whitelist(project, chain, deployer, alice, bootstrap):
    protocol = project.MockToken.deploy(sender=deployer)
    chain.pending_timestamp += WEEK_LENGTH
    bootstrap.apply(protocol, value=ONE, sender=alice)
    
    chain.pending_timestamp += WEEK_LENGTH
    incentive = project.MockToken.deploy(sender=deployer)
    with ape.reverts(dev_message='dev: not whitelisted'):
        bootstrap.incentivize(protocol, incentive, ONE, sender=alice)

def test_incentivize(project, chain, deployer, alice, bootstrap):
    protocol = project.MockToken.deploy(sender=deployer)
    chain.pending_timestamp += WEEK_LENGTH
    bootstrap.apply(protocol, value=ONE, sender=alice)
    bootstrap.whitelist(protocol, sender=deployer)

    chain.pending_timestamp += WEEK_LENGTH
    incentive = project.MockToken.deploy(sender=deployer)
    incentive.mint(alice, ONE, sender=deployer)
    incentive.approve(bootstrap, MAX, sender=alice)

    assert bootstrap.incentives(protocol, incentive) == 0
    assert bootstrap.incentive_depositors(protocol, incentive, alice) == 0
    bootstrap.incentivize(protocol, incentive, ONE, sender=alice)
    assert bootstrap.incentives(protocol, incentive) == ONE
    assert bootstrap.incentive_depositors(protocol, incentive, alice) == ONE

def test_incentivize_multiple(project, chain, deployer, alice, bootstrap):
    protocol = project.MockToken.deploy(sender=deployer)
    chain.pending_timestamp += WEEK_LENGTH
    bootstrap.apply(protocol, value=ONE, sender=alice)
    bootstrap.whitelist(protocol, sender=deployer)

    chain.pending_timestamp += WEEK_LENGTH
    incentive = project.MockToken.deploy(sender=deployer)
    incentive.mint(alice, 3 * ONE, sender=deployer)
    incentive.approve(bootstrap, MAX, sender=alice)

    bootstrap.incentivize(protocol, incentive, ONE, sender=alice)
    bootstrap.incentivize(protocol, incentive, 2 * ONE, sender=alice)
    assert bootstrap.incentives(protocol, incentive) == 3 * ONE
    assert bootstrap.incentive_depositors(protocol, incentive, alice) == 3 * ONE

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

def test_deposit_multiple(chain, alice, staking, bootstrap):
    chain.pending_timestamp += 3 * WEEK_LENGTH
    alice.transfer(bootstrap, ONE)
    alice.transfer(bootstrap, 2 * ONE)
    assert bootstrap.debt() == 3 * ONE
    assert bootstrap.deposited() == 3 * ONE
    assert bootstrap.deposits(alice) == 3 * ONE
    assert staking.balanceOf(bootstrap) == 3 * ONE

def test_split_management(chain, deployer, treasury, pol, alice, bootstrap):
    chain.pending_timestamp += 3 * WEEK_LENGTH
    tb = treasury.balance
    pb = pol.balance
    alice.transfer(bootstrap, ONE)
    with ape.reverts():
        bootstrap.split(sender=alice)
    bootstrap.split(sender=deployer)
    assert treasury.balance - tb == ONE * 9 // 10
    assert pol.balance - pb == ONE // 10

def test_split_treasury(chain, treasury, pol, alice, bootstrap):
    chain.pending_timestamp += 3 * WEEK_LENGTH
    tb = treasury.balance
    pb = pol.balance
    alice.transfer(bootstrap, ONE)
    tx = bootstrap.split(sender=treasury)
    assert treasury.balance - tb + tx.total_fees_paid == ONE * 9 // 10
    assert pol.balance - pb == ONE // 10

def test_repay(chain, deployer, alice, bob, token, bootstrap):
    chain.pending_timestamp += 3 * WEEK_LENGTH
    alice.transfer(bootstrap, 3 * ONE)
    token.set_minter(deployer, sender=deployer)
    token.mint(bob, 2 * ONE, sender=deployer)
    with ape.reverts():
        bootstrap.repay(2 * ONE, sender=bob)
    token.approve(bootstrap, MAX, sender=bob)
    bootstrap.repay(2 * ONE, sender=bob)
    assert token.balanceOf(bob) == 0
    assert token.balanceOf(bootstrap) == 0
    assert bootstrap.debt() == ONE

def test_vote_early_late(project, chain, deployer, alice, bootstrap):
    protocol = project.MockToken.deploy(sender=deployer)
    
    with ape.reverts(dev_message='dev: outside vote period'):
        bootstrap.vote([protocol], [ONE], sender=alice)

    chain.pending_timestamp += 5 * WEEK_LENGTH
    with ape.reverts(dev_message='dev: outside vote period'):
        bootstrap.vote([protocol], [ONE], sender=alice)

def test_vote_no_application(project, chain, deployer, alice, bootstrap):
    protocol = project.MockToken.deploy(sender=deployer)

    chain.pending_timestamp += 3 * WEEK_LENGTH
    alice.transfer(bootstrap, ONE)

    chain.pending_timestamp += WEEK_LENGTH
    with ape.reverts(dev_message='dev: protocol not whitelisted'):
        bootstrap.vote([protocol], [ONE], sender=alice)

def test_vote_no_whitelist(project, chain, deployer, alice, bootstrap):
    protocol = project.MockToken.deploy(sender=deployer)

    chain.pending_timestamp += WEEK_LENGTH
    bootstrap.apply(protocol, value=ONE, sender=alice)

    chain.pending_timestamp += 2 * WEEK_LENGTH
    alice.transfer(bootstrap, ONE)

    chain.pending_timestamp += WEEK_LENGTH
    with ape.reverts(dev_message='dev: protocol not whitelisted'):
        bootstrap.vote([protocol], [ONE], sender=alice)

def test_vote_exceed(project, chain, deployer, alice, bootstrap):
    protocol = project.MockToken.deploy(sender=deployer)
    
    chain.pending_timestamp += WEEK_LENGTH
    bootstrap.apply(protocol, value=ONE, sender=alice)
    bootstrap.whitelist(protocol, sender=deployer)

    chain.pending_timestamp += 2 * WEEK_LENGTH
    alice.transfer(bootstrap, ONE)

    chain.pending_timestamp += WEEK_LENGTH
    with ape.reverts(dev_message='dev: too many votes'):
        bootstrap.vote([protocol], [ONE + 1], sender=alice)

def test_vote(project, chain, deployer, alice, bootstrap):
    protocol = project.MockToken.deploy(sender=deployer)
    
    chain.pending_timestamp += WEEK_LENGTH
    bootstrap.apply(protocol, value=ONE, sender=alice)
    bootstrap.whitelist(protocol, sender=deployer)

    chain.pending_timestamp += 2 * WEEK_LENGTH
    alice.transfer(bootstrap, ONE)

    chain.pending_timestamp += WEEK_LENGTH
    chain.mine()
    assert bootstrap.voted() == 0
    assert bootstrap.votes_used(alice) == 0
    assert bootstrap.votes_used_protocol(alice, protocol) == 0
    assert bootstrap.votes(protocol) == 0
    assert bootstrap.votes_available(alice) == ONE

    bootstrap.vote([protocol], [ONE], sender=alice)
    assert bootstrap.voted() == ONE
    assert bootstrap.votes_used(alice) == ONE
    assert bootstrap.votes_used_protocol(alice, protocol) == ONE
    assert bootstrap.votes(protocol) == ONE
    assert bootstrap.votes_available(alice) == 0

def test_vote_many_exceed(project, chain, deployer, alice, bootstrap):
    protocol1 = project.MockToken.deploy(sender=deployer)
    protocol2 = project.MockToken.deploy(sender=deployer)
    
    chain.pending_timestamp += WEEK_LENGTH
    bootstrap.apply(protocol1, value=ONE, sender=alice)
    bootstrap.apply(protocol2, value=ONE, sender=alice)
    bootstrap.whitelist(protocol1, sender=deployer)
    bootstrap.whitelist(protocol2, sender=deployer)

    chain.pending_timestamp += 2 * WEEK_LENGTH
    alice.transfer(bootstrap, 2 * ONE)

    chain.pending_timestamp += WEEK_LENGTH
    with ape.reverts(dev_message='dev: too many votes'):
        bootstrap.vote([protocol1, protocol2], [ONE, 2 * ONE], sender=alice)

def test_vote_many(project, chain, deployer, alice, bootstrap):
    protocol1 = project.MockToken.deploy(sender=deployer)
    protocol2 = project.MockToken.deploy(sender=deployer)
    
    chain.pending_timestamp += WEEK_LENGTH
    bootstrap.apply(protocol1, value=ONE, sender=alice)
    bootstrap.apply(protocol2, value=ONE, sender=alice)
    bootstrap.whitelist(protocol1, sender=deployer)
    bootstrap.whitelist(protocol2, sender=deployer)

    chain.pending_timestamp += 2 * WEEK_LENGTH
    alice.transfer(bootstrap, 3 * ONE)

    chain.pending_timestamp += WEEK_LENGTH
    bootstrap.vote([protocol1, protocol2], [ONE, 2 * ONE], sender=alice)
    assert bootstrap.voted() == 3 * ONE
    assert bootstrap.votes_used(alice) == 3 * ONE
    assert bootstrap.votes(protocol1) == ONE
    assert bootstrap.votes(protocol2) == 2 * ONE
    assert bootstrap.votes_available(alice) == 0

def test_vote_multiple_exceed(project, chain, deployer, alice, bootstrap):
    protocol = project.MockToken.deploy(sender=deployer)
    
    chain.pending_timestamp += WEEK_LENGTH
    bootstrap.apply(protocol, value=ONE, sender=alice)
    bootstrap.whitelist(protocol, sender=deployer)

    chain.pending_timestamp += 2 * WEEK_LENGTH
    alice.transfer(bootstrap, 2 * ONE)

    chain.pending_timestamp += WEEK_LENGTH
    bootstrap.vote([protocol], [ONE], sender=alice)
    with ape.reverts(dev_message='dev: too many votes'):
        bootstrap.vote([protocol], [2 * ONE], sender=alice)

def test_vote_multiple(project, chain, deployer, alice, bootstrap):
    protocol = project.MockToken.deploy(sender=deployer)
    
    chain.pending_timestamp += WEEK_LENGTH
    bootstrap.apply(protocol, value=ONE, sender=alice)
    bootstrap.whitelist(protocol, sender=deployer)

    chain.pending_timestamp += 2 * WEEK_LENGTH
    alice.transfer(bootstrap, 3 * ONE)

    chain.pending_timestamp += WEEK_LENGTH
    bootstrap.vote([protocol], [ONE], sender=alice)
    assert bootstrap.votes_available(alice) == 2 * ONE
    bootstrap.vote([protocol], [2 * ONE], sender=alice)
    assert bootstrap.voted() == 3 * ONE
    assert bootstrap.votes_used(alice) == 3 * ONE
    assert bootstrap.votes_used_protocol(alice, protocol) == 3 * ONE
    assert bootstrap.votes(protocol) == 3 * ONE
    assert bootstrap.votes_available(alice) == 0

def test_undo_vote(project, chain, deployer, alice, bob, bootstrap):
    protocol = project.MockToken.deploy(sender=deployer)
    
    chain.pending_timestamp += WEEK_LENGTH
    bootstrap.apply(protocol, value=ONE, sender=alice)
    bootstrap.whitelist(protocol, sender=deployer)

    chain.pending_timestamp += 2 * WEEK_LENGTH
    alice.transfer(bootstrap, ONE)

    chain.pending_timestamp += WEEK_LENGTH
    bootstrap.vote([protocol], [ONE], sender=alice)

    with ape.reverts():
        bootstrap.undo_vote(protocol, alice, sender=bob)

    bootstrap.undo_whitelist(protocol, sender=deployer)
    bootstrap.undo_vote(protocol, alice, sender=bob)
    assert bootstrap.voted() == 0
    assert bootstrap.votes_used(alice) == 0
    assert bootstrap.votes_used_protocol(alice, protocol) == 0
    assert bootstrap.votes(protocol) == 0
    assert bootstrap.votes_available(alice) == ONE


def test_declare_early(project, chain, deployer, alice, bootstrap):
    protocol = project.MockToken.deploy(sender=deployer)
    
    chain.pending_timestamp += WEEK_LENGTH
    bootstrap.apply(protocol, value=ONE, sender=alice)
    bootstrap.whitelist(protocol, sender=deployer)

    chain.pending_timestamp += 3 * WEEK_LENGTH
    with ape.reverts():
        bootstrap.declare_winners([protocol], sender=deployer)

def test_declare_multiple(project, chain, deployer, alice, bootstrap):
    protocol1 = project.MockToken.deploy(sender=deployer)
    protocol2 = project.MockToken.deploy(sender=deployer)
    
    chain.pending_timestamp += WEEK_LENGTH
    bootstrap.apply(protocol1, value=ONE, sender=alice)
    bootstrap.apply(protocol2, value=ONE, sender=alice)
    bootstrap.whitelist(protocol1, sender=deployer)
    bootstrap.whitelist(protocol2, sender=deployer)

    chain.pending_timestamp += 4 * WEEK_LENGTH
    bootstrap.declare_winners([protocol1], sender=deployer)
    with ape.reverts():
        bootstrap.declare_winners([protocol2], sender=deployer)

def test_declare_duplicate(project, chain, deployer, alice, bootstrap):
    protocol = project.MockToken.deploy(sender=deployer)
    
    chain.pending_timestamp += WEEK_LENGTH
    bootstrap.apply(protocol, value=ONE, sender=alice)
    bootstrap.whitelist(protocol, sender=deployer)

    chain.pending_timestamp += 4 * WEEK_LENGTH
    with ape.reverts():
        bootstrap.declare_winners([protocol, protocol], sender=deployer)

def test_declare(project, chain, deployer, alice, bootstrap):
    protocol = project.MockToken.deploy(sender=deployer)
    
    chain.pending_timestamp += WEEK_LENGTH
    bootstrap.apply(protocol, value=ONE, sender=alice)
    bootstrap.whitelist(protocol, sender=deployer)

    chain.pending_timestamp += 4 * WEEK_LENGTH
    assert bootstrap.num_winners() == 0
    assert not bootstrap.winners(protocol)
    bootstrap.declare_winners([protocol], sender=deployer)
    assert bootstrap.num_winners() == 1
    assert bootstrap.winners(protocol)
    assert bootstrap.winners_list(0) == protocol

def test_declare_many(project, chain, deployer, alice, bootstrap):
    protocol1 = project.MockToken.deploy(sender=deployer)
    protocol2 = project.MockToken.deploy(sender=deployer)
    
    chain.pending_timestamp += WEEK_LENGTH
    bootstrap.apply(protocol1, value=ONE, sender=alice)
    bootstrap.apply(protocol2, value=ONE, sender=alice)
    bootstrap.whitelist(protocol1, sender=deployer)
    bootstrap.whitelist(protocol2, sender=deployer)

    chain.pending_timestamp += 4 * WEEK_LENGTH
    bootstrap.declare_winners([protocol1, protocol2], sender=deployer)
    assert bootstrap.num_winners() == 2
    assert bootstrap.winners(protocol1)
    assert bootstrap.winners(protocol2)
    assert bootstrap.winners_list(0) == protocol1
    assert bootstrap.winners_list(1) == protocol2

def test_claim_incentive_loser(project, chain, deployer, alice, bob, bootstrap):
    protocol1 = project.MockToken.deploy(sender=deployer)
    protocol2 = project.MockToken.deploy(sender=deployer)
    incentive = project.MockToken.deploy(sender=deployer)
    
    chain.pending_timestamp += WEEK_LENGTH
    bootstrap.apply(protocol1, value=ONE, sender=alice)
    bootstrap.apply(protocol2, value=ONE, sender=alice)
    bootstrap.whitelist(protocol1, sender=deployer)
    bootstrap.whitelist(protocol2, sender=deployer)

    chain.pending_timestamp += WEEK_LENGTH
    incentive.approve(bootstrap, MAX, sender=deployer)
    incentive.mint(deployer, ONE, sender=deployer)
    bootstrap.incentivize(protocol1, incentive, ONE, sender=deployer)

    chain.pending_timestamp += WEEK_LENGTH
    alice.transfer(bootstrap, ONE)

    chain.pending_timestamp += WEEK_LENGTH
    bootstrap.vote([protocol1], [ONE], sender=alice)

    chain.pending_timestamp += WEEK_LENGTH
    bootstrap.declare_winners([protocol2], sender=deployer)

    with ape.reverts(dev_message='dev: protocol is not winner'):
        bootstrap.claim_incentive(protocol1, incentive, alice, sender=bob)

def test_claim_incentive_not_voted(project, chain, deployer, alice, bob, bootstrap):
    protocol = project.MockToken.deploy(sender=deployer)
    incentive = project.MockToken.deploy(sender=deployer)
    
    chain.pending_timestamp += WEEK_LENGTH
    bootstrap.apply(protocol, value=ONE, sender=alice)
    bootstrap.whitelist(protocol, sender=deployer)

    chain.pending_timestamp += WEEK_LENGTH
    incentive.approve(bootstrap, MAX, sender=deployer)
    incentive.mint(deployer, ONE, sender=deployer)
    bootstrap.incentivize(protocol, incentive, ONE, sender=deployer)

    chain.pending_timestamp += WEEK_LENGTH
    alice.transfer(bootstrap, ONE)
    bob.transfer(bootstrap, ONE)

    chain.pending_timestamp += WEEK_LENGTH
    bootstrap.vote([protocol], [ONE], sender=bob)

    chain.pending_timestamp += WEEK_LENGTH
    bootstrap.declare_winners([protocol], sender=deployer)
    
    with ape.reverts(dev_message='dev: nothing to claim'):
        bootstrap.claim_incentive(protocol, incentive, alice, sender=bob)

def test_claim_incentive(project, chain, deployer, alice, bob, bootstrap):
    protocol = project.MockToken.deploy(sender=deployer)
    incentive = project.MockToken.deploy(sender=deployer)
    
    chain.pending_timestamp += WEEK_LENGTH
    bootstrap.apply(protocol, value=ONE, sender=alice)
    bootstrap.whitelist(protocol, sender=deployer)

    chain.pending_timestamp += WEEK_LENGTH
    incentive.approve(bootstrap, MAX, sender=deployer)
    incentive.mint(deployer, 6 * ONE, sender=deployer)
    bootstrap.incentivize(protocol, incentive, 6 * ONE, sender=deployer)

    chain.pending_timestamp += WEEK_LENGTH
    alice.transfer(bootstrap, ONE)
    bob.transfer(bootstrap, 2 * ONE)

    chain.pending_timestamp += WEEK_LENGTH
    bootstrap.vote([protocol], [ONE], sender=alice)
    bootstrap.vote([protocol], [2 * ONE], sender=bob)

    chain.pending_timestamp += WEEK_LENGTH
    bootstrap.declare_winners([protocol], sender=deployer)
    
    assert not bootstrap.incentive_claimed(protocol, incentive, alice)
    assert bootstrap.claimable_incentive(protocol, incentive, alice) == 2 * ONE
    assert incentive.balanceOf(alice) == 0
    bootstrap.claim_incentive(protocol, incentive, alice, sender=bob)
    assert bootstrap.incentive_claimed(protocol, incentive, alice)
    assert bootstrap.claimable_incentive(protocol, incentive, alice) == 0
    assert incentive.balanceOf(alice) == 2 * ONE

def test_claim_incentive_other_vote(project, chain, deployer, alice, bob, bootstrap):
    protocol1 = project.MockToken.deploy(sender=deployer)
    protocol2 = project.MockToken.deploy(sender=deployer)
    incentive = project.MockToken.deploy(sender=deployer)
    
    chain.pending_timestamp += WEEK_LENGTH
    bootstrap.apply(protocol1, value=ONE, sender=alice)
    bootstrap.apply(protocol2, value=ONE, sender=alice)
    bootstrap.whitelist(protocol1, sender=deployer)
    bootstrap.whitelist(protocol2, sender=deployer)

    chain.pending_timestamp += WEEK_LENGTH
    incentive.approve(bootstrap, MAX, sender=deployer)
    incentive.mint(deployer, ONE, sender=deployer)
    bootstrap.incentivize(protocol1, incentive, ONE, sender=deployer)

    chain.pending_timestamp += WEEK_LENGTH
    alice.transfer(bootstrap, ONE)

    chain.pending_timestamp += WEEK_LENGTH
    bootstrap.vote([protocol2], [ONE], sender=alice)

    chain.pending_timestamp += WEEK_LENGTH
    bootstrap.declare_winners([protocol1, protocol2], sender=deployer)
    
    assert bootstrap.claimable_incentive(protocol1, incentive, alice) == ONE
    bootstrap.claim_incentive(protocol1, incentive, alice, sender=bob)
    assert incentive.balanceOf(alice) == ONE
