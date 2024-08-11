from algopy import ARC4Contract, Account, Asset, gtxn, Global, LocalState, Txn, UInt64, itxn
from algopy.arc4 import abimethod


class Auction(ARC4Contract):
    def __init__(self) -> None:
        self.end_time = UInt64()
        self.asa = Asset()  # Tài sản đấu giá
        self.asa_amount = UInt64()  # Số tiền đấu giá
        self.previous_bidder = Account()
        self.previous_bid = UInt64()
        self.claimable_amount = LocalState(UInt64, key='claim', description='The claimable amount')

    @abimethod
    def opt_in_asset(self, asset: Asset) -> None:
        assert Txn.sender == Global.creator_address, 'Only creator can opt in to ASA'
        assert self.asa.id == 0, 'ASA already opted in'
        self.asa = asset

        # Opt in asset
        itxn.AssetTransfer(xfer_asset=asset, asset_receiver=Global.current_application_address).submit()

    @abimethod
    def start_auction(self, starting_price: UInt64, duration: UInt64, axfer: gtxn.AssetTransferTransaction) -> None:
        assert Txn.sender == Global.creator_address, 'Must be started by creator of auction'
        assert self.end_time == 0, 'Auction started'
        assert axfer.asset_receiver == Global.current_application_address, 'Axfer must transfer to this app'

        # set global state
        self.asa_amount = axfer.asset_amount
        self.previous_bid = starting_price
        self.end_time = Global.latest_timestamp + duration

    @abimethod
    def bid(self, pay: gtxn.PaymentTransaction) -> None:
        # Kiểm tra đấu giá đã kết thúc chưa
        assert Global.latest_timestamp < self.end_time, 'Auction ended'

        # Verify payment
        assert Txn.sender != self.previous_bidder, 'Must not previous bidder'
        assert Txn.sender == pay.sender, 'Verify again'
        assert pay.amount > self.previous_bid, 'Must greater than asa amount'

        # Set data on global state
        self.previous_bid = pay.amount
        self.previous_bidder = pay.sender

        # Update claimable amount
        self.claimable_amount[Txn.sender] = pay.amount

    @abimethod
    def claim_asset(self, asset: Asset) -> None:
        assert Global.latest_timestamp > self.end_time, 'Auction not ended yet'

        # Chuyển tài sản cho người trúng đấu giá
        itxn.AssetTransfer(xfer_asset=asset, asset_receiver=self.previous_bidder, asset_amount=self.asa_amount,
                           asset_close_to=self.previous_bidder).submit()

    @abimethod
    def claim_bids(self) -> None:
        amount = original_amount = self.claimable_amount[Txn.sender]
        # Khấu trừ số token đã trúng đấu giá
        if Txn.sender == self.previous_bidder:
            amount -= self.previous_bid

        # Trả lại số token không trúng đấu giá
        itxn.Payment(receiver=Txn.sender, amount=amount).submit()
        self.claimable_amount[Txn.sender] = original_amount - amount

    @abimethod(allow_actions=['DeleteApplication'])
    def delete_application(self) -> None:
        # Đóng đấu giá
        itxn.Payment(receiver=Global.creator_address, close_remainder_to=Global.creator_address).submit()

    def clear_state_program(self) -> bool:
        return True
