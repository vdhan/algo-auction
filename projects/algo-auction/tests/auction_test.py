from collections.abc import Generator
from time import time

import pytest
from algopy_testing import AlgopyTestContext, algopy_testing_context

from smart_contracts.auction.contract import Auction


@pytest.fixture()
def context() -> Generator[AlgopyTestContext, None, None]:
    with algopy_testing_context() as ctx:
        yield ctx
        ctx.reset()


def test_opt_in_asset(context: AlgopyTestContext) -> None:
    asset = context.any_asset()
    contract = Auction()
    contract.opt_in_asset(asset)
    inner_txn = context.last_submitted_itxn.asset_transfer

    assert contract.asa.id == asset.id
    assert inner_txn.asset_receiver == context.default_application.address
    assert inner_txn.xfer_asset == asset


def test_start_auction(context: AlgopyTestContext) -> None:
    start_price = context.any_uint64(1, 100)
    axfer = context.any_asset_transfer_transaction(
        asset_amount=start_price, asset_receiver=context.default_application.address)

    current = context.any_uint64(1, 1000)
    context.patch_global_fields(latest_timestamp=current)
    context.patch_txn_fields(sender=context.default_creator)

    duration = context.any_uint64(100, 1000)
    contract = Auction()
    contract.start_auction(start_price, duration, axfer)

    assert contract.asa_amount == start_price
    assert contract.previous_bid == start_price
    assert contract.end_time == current + duration


def test_bid(context: AlgopyTestContext) -> None:
    account = context.any_account()
    context.patch_txn_fields(sender=account)

    amount = context.any_uint64(100, 1000)
    pay = context.any_payment_transaction(sender=account, amount=amount)

    end_time = context.any_uint64(int(time() + 10000))
    start_price = context.any_uint64(1, 100)
    contract = Auction()
    contract.end_time = end_time
    contract.previous_bid = start_price
    contract.bid(pay)

    assert contract.previous_bid == amount
    assert contract.previous_bidder == account
    assert contract.claimable_amount[account] == amount


def test_claim_bids(context: AlgopyTestContext) -> None:
    account = context.any_account()
    context.patch_txn_fields(sender=account)

    claimable_amount = context.any_uint64(10)
    previous_bid = context.any_uint64(1, int(claimable_amount))
    contract = Auction()
    contract.claimable_amount[account] = claimable_amount
    contract.previous_bidder = account
    contract.previous_bid = previous_bid
    contract.claim_bids()

    amount = claimable_amount - previous_bid
    last_txn = context.last_submitted_itxn.payment

    assert last_txn.amount == amount
    assert last_txn.receiver == account
    assert contract.claimable_amount[account] == claimable_amount - amount
