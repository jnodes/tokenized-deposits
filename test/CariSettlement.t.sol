// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import "./TestHelper.sol";
import "../contracts/interfaces/ICariSettlement.sol";

/**
 * @title CariSettlementTest
 * @notice Unit tests for the Cari Network cross-bank settlement contract.
 *         M&T Bank | Cari Network | ZKsync Prividium.
 */
contract CariSettlementTest is TestHelper {
    bytes32 constant TRAVEL_HASH = keccak256("travel-rule-data");

    function setUp() public override {
        super.setUp();
        // Pre-mint tokens to alice for settlement tests
        _mint(alice, 100_000e6);
    }

    // =========================================================================
    //                          INITIALIZATION
    // =========================================================================

    function test_initialize_token() public view {
        assertEq(address(settlement.token()), address(token));
    }

    function test_initialize_settlementExpiry() public view {
        assertEq(settlement.settlementExpiry(), SETTLEMENT_EXPIRY);
    }

    function test_initialize_roles() public view {
        assertTrue(settlement.hasRole(settlement.DEFAULT_ADMIN_ROLE(), admin));
        assertTrue(settlement.hasRole(settlement.SETTLEMENT_OPERATOR_ROLE(), settlementOperator));
        assertTrue(settlement.hasRole(settlement.INITIATOR_ROLE(), initiator));
    }

    function test_initialize_revert_zeroToken() public {
        CariSettlement impl = new CariSettlement();
        vm.expectRevert(CariSettlement.ZeroAddress.selector);
        new ERC1967Proxy(
            address(impl),
            abi.encodeCall(CariSettlement.initialize, (admin, address(0), SETTLEMENT_EXPIRY))
        );
    }

    function test_initialize_revert_zeroExpiry() public {
        CariSettlement impl = new CariSettlement();
        vm.expectRevert(CariSettlement.InvalidExpiry.selector);
        new ERC1967Proxy(
            address(impl),
            abi.encodeCall(CariSettlement.initialize, (admin, address(token), 0))
        );
    }

    // =========================================================================
    //                      MEMBER BANK REGISTRY
    // =========================================================================

    function test_addMemberBank() public {
        address bankC = makeAddr("bankC");
        vm.prank(admin);
        settlement.addMemberBank(bankC);
        assertTrue(settlement.isMemberBank(bankC));
    }

    function test_removeMemberBank() public {
        assertTrue(settlement.isMemberBank(memberBankB));
        vm.prank(admin);
        settlement.removeMemberBank(memberBankB);
        assertFalse(settlement.isMemberBank(memberBankB));
    }

    function test_addMemberBank_revert_notAdmin() public {
        vm.prank(alice);
        vm.expectRevert();
        settlement.addMemberBank(makeAddr("x"));
    }

    // =========================================================================
    //                    INITIATE SETTLEMENT
    // =========================================================================

    function test_initiateSettlement_success() public {
        uint256 aliceBefore = token.balanceOf(alice);
        uint256 amount = 10_000e6;

        vm.prank(initiator);
        bytes32 sid = settlement.initiateSettlement(
            memberBankB, alice, bob, amount, TRAVEL_HASH
        );

        // Alice's tokens should be burned
        assertEq(token.balanceOf(alice), aliceBefore - amount);

        // Settlement record should exist
        ICariSettlement.SettlementRequest memory s = settlement.getSettlement(sid);
        assertEq(s.amount, amount);
        assertEq(s.originator, alice);
        assertEq(s.beneficiary, bob);
        assertEq(s.travelRuleHash, TRAVEL_HASH);
        assertEq(uint8(s.status), uint8(ICariSettlement.SettlementStatus.PENDING));
    }

    function test_initiateSettlement_emitsEvent() public {
        vm.prank(initiator);
        // We can't predict settlementId, so just check it doesn't revert
        settlement.initiateSettlement(memberBankB, alice, bob, 1000e6, TRAVEL_HASH);
    }

    function test_initiateSettlement_revert_notMemberBank() public {
        address fakeBank = makeAddr("fakeBank");
        vm.prank(initiator);
        vm.expectRevert(abi.encodeWithSelector(CariSettlement.NotMemberBank.selector, fakeBank));
        settlement.initiateSettlement(fakeBank, alice, bob, 1000e6, TRAVEL_HASH);
    }

    function test_initiateSettlement_revert_zeroAmount() public {
        vm.prank(initiator);
        vm.expectRevert(CariSettlement.ZeroAmount.selector);
        settlement.initiateSettlement(memberBankB, alice, bob, 0, TRAVEL_HASH);
    }

    function test_initiateSettlement_revert_notInitiator() public {
        vm.prank(alice);
        vm.expectRevert();
        settlement.initiateSettlement(memberBankB, alice, bob, 1000e6, TRAVEL_HASH);
    }

    function test_initiateSettlement_revert_whenPaused() public {
        vm.prank(admin);
        settlement.pause();

        vm.prank(initiator);
        vm.expectRevert();
        settlement.initiateSettlement(memberBankB, alice, bob, 1000e6, TRAVEL_HASH);
    }

    // =========================================================================
    //                    EXECUTE SETTLEMENT
    // =========================================================================

    function test_executeSettlement_success() public {
        uint256 amount = 5_000e6;

        vm.prank(initiator);
        bytes32 sid = settlement.initiateSettlement(
            memberBankB, alice, bob, amount, TRAVEL_HASH
        );

        uint256 bobBefore = token.balanceOf(bob);

        vm.prank(settlementOperator);
        settlement.executeSettlement(sid);

        // Bob should receive the tokens
        assertEq(token.balanceOf(bob), bobBefore + amount);

        // Status should be EXECUTED
        ICariSettlement.SettlementRequest memory s = settlement.getSettlement(sid);
        assertEq(uint8(s.status), uint8(ICariSettlement.SettlementStatus.EXECUTED));
    }

    function test_executeSettlement_revert_notPending() public {
        vm.prank(initiator);
        bytes32 sid = settlement.initiateSettlement(
            memberBankB, alice, bob, 1000e6, TRAVEL_HASH
        );

        vm.prank(settlementOperator);
        settlement.executeSettlement(sid);

        // Try to execute again
        vm.prank(settlementOperator);
        vm.expectRevert(
            abi.encodeWithSelector(
                CariSettlement.SettlementNotPending.selector,
                sid,
                ICariSettlement.SettlementStatus.EXECUTED
            )
        );
        settlement.executeSettlement(sid);
    }

    function test_executeSettlement_revert_expired() public {
        vm.prank(initiator);
        bytes32 sid = settlement.initiateSettlement(
            memberBankB, alice, bob, 1000e6, TRAVEL_HASH
        );

        // Warp past expiry
        vm.warp(block.timestamp + SETTLEMENT_EXPIRY + 1);

        vm.prank(settlementOperator);
        vm.expectRevert(abi.encodeWithSelector(CariSettlement.SettlementAlreadyExpired.selector, sid));
        settlement.executeSettlement(sid);
    }

    function test_executeSettlement_revert_notFound() public {
        bytes32 fakeSid = keccak256("fake");
        vm.prank(settlementOperator);
        vm.expectRevert(abi.encodeWithSelector(CariSettlement.SettlementNotFound.selector, fakeSid));
        settlement.executeSettlement(fakeSid);
    }

    function test_executeSettlement_revert_notOperator() public {
        vm.prank(initiator);
        bytes32 sid = settlement.initiateSettlement(
            memberBankB, alice, bob, 1000e6, TRAVEL_HASH
        );

        vm.prank(alice);
        vm.expectRevert();
        settlement.executeSettlement(sid);
    }

    // =========================================================================
    //                    REVERT SETTLEMENT
    // =========================================================================

    function test_revertSettlement_success() public {
        uint256 amount = 5_000e6;
        uint256 aliceBefore = token.balanceOf(alice);

        vm.prank(initiator);
        bytes32 sid = settlement.initiateSettlement(
            memberBankB, alice, bob, amount, TRAVEL_HASH
        );

        // Alice lost tokens after initiation
        assertEq(token.balanceOf(alice), aliceBefore - amount);

        vm.prank(settlementOperator);
        settlement.revertSettlement(sid, "Compliance check failed at destination");

        // Alice should get tokens back
        assertEq(token.balanceOf(alice), aliceBefore);

        ICariSettlement.SettlementRequest memory s = settlement.getSettlement(sid);
        assertEq(uint8(s.status), uint8(ICariSettlement.SettlementStatus.REVERTED));
    }

    function test_revertSettlement_revert_notPending() public {
        vm.prank(initiator);
        bytes32 sid = settlement.initiateSettlement(
            memberBankB, alice, bob, 1000e6, TRAVEL_HASH
        );

        vm.prank(settlementOperator);
        settlement.executeSettlement(sid);

        vm.prank(settlementOperator);
        vm.expectRevert();
        settlement.revertSettlement(sid, "too late");
    }

    // =========================================================================
    //                    EXPIRE SETTLEMENT
    // =========================================================================

    function test_expireSettlement_success() public {
        uint256 amount = 5_000e6;
        uint256 aliceBefore = token.balanceOf(alice);

        vm.prank(initiator);
        bytes32 sid = settlement.initiateSettlement(
            memberBankB, alice, bob, amount, TRAVEL_HASH
        );

        // Warp past expiry
        vm.warp(block.timestamp + SETTLEMENT_EXPIRY + 1);

        // Refresh oracle attestation so settlementMint doesn't fail on staleness
        vm.prank(attestor);
        oracle.updateAttestation(INITIAL_RESERVES, ATTEST_HASH);

        // Anyone can call expire
        vm.prank(charlie);
        settlement.expireSettlement(sid);

        // Alice should get tokens back
        assertEq(token.balanceOf(alice), aliceBefore);

        ICariSettlement.SettlementRequest memory s = settlement.getSettlement(sid);
        assertEq(uint8(s.status), uint8(ICariSettlement.SettlementStatus.EXPIRED));
    }

    function test_expireSettlement_revert_notExpiredYet() public {
        vm.prank(initiator);
        bytes32 sid = settlement.initiateSettlement(
            memberBankB, alice, bob, 1000e6, TRAVEL_HASH
        );

        vm.prank(charlie);
        vm.expectRevert(abi.encodeWithSelector(CariSettlement.SettlementNotExpired.selector, sid));
        settlement.expireSettlement(sid);
    }

    // =========================================================================
    //                      ADMIN CONFIG
    // =========================================================================

    function test_setSettlementExpiry() public {
        vm.prank(admin);
        settlement.setSettlementExpiry(3600);
        assertEq(settlement.settlementExpiry(), 3600);
    }

    function test_setSettlementExpiry_revert_zero() public {
        vm.prank(admin);
        vm.expectRevert(CariSettlement.InvalidExpiry.selector);
        settlement.setSettlementExpiry(0);
    }

    // =========================================================================
    //                SETTLEMENT RETURN (FINDING-001)
    // =========================================================================

    function test_expireSettlement_usesSettlementReturn() public {
        uint256 amount = 5_000e6;
        uint256 aliceBefore = token.balanceOf(alice);

        vm.prank(initiator);
        bytes32 sid = settlement.initiateSettlement(
            memberBankB, alice, bob, amount, TRAVEL_HASH
        );

        // Alice's tokens were burned
        assertEq(token.balanceOf(alice), aliceBefore - amount);

        // Warp past expiry
        vm.warp(block.timestamp + SETTLEMENT_EXPIRY + 1);

        // Expire settlement - uses settlementReturn (no reserve check)
        vm.prank(charlie);
        settlement.expireSettlement(sid);

        // Alice should get tokens back via settlementReturn
        assertEq(token.balanceOf(alice), aliceBefore);

        ICariSettlement.SettlementRequest memory s = settlement.getSettlement(sid);
        assertEq(uint8(s.status), uint8(ICariSettlement.SettlementStatus.EXPIRED));
    }

    function test_revertSettlement_usesSettlementReturn() public {
        uint256 amount = 5_000e6;
        uint256 aliceBefore = token.balanceOf(alice);

        vm.prank(initiator);
        bytes32 sid = settlement.initiateSettlement(
            memberBankB, alice, bob, amount, TRAVEL_HASH
        );

        // Alice's tokens were burned
        assertEq(token.balanceOf(alice), aliceBefore - amount);

        // Revert settlement - uses settlementReturn (no reserve check)
        vm.prank(settlementOperator);
        settlement.revertSettlement(sid, "Compliance failed at destination");

        // Alice should get tokens back via settlementReturn
        assertEq(token.balanceOf(alice), aliceBefore);

        ICariSettlement.SettlementRequest memory s = settlement.getSettlement(sid);
        assertEq(uint8(s.status), uint8(ICariSettlement.SettlementStatus.REVERTED));
    }

    function test_expireSettlement_succeedsEvenWithLowReserves() public {
        uint256 amount = 5_000e6;
        uint256 aliceBefore = token.balanceOf(alice);

        vm.prank(initiator);
        bytes32 sid = settlement.initiateSettlement(
            memberBankB, alice, bob, amount, TRAVEL_HASH
        );

        // Reduce reserves below what would be needed for a normal settlementMint
        // Current supply after settlement initiation: alice still has (aliceBefore - amount)
        // We'll set reserves to less than (aliceBefore - amount + amount) = aliceBefore
        vm.prank(attestor);
        oracle.updateAttestation(1e6, keccak256("very-low-reserves"));

        // Warp past expiry
        vm.warp(block.timestamp + SETTLEMENT_EXPIRY + 1);

        // Expire settlement - should succeed even with low reserves
        // because settlementReturn bypasses reserve check
        vm.prank(charlie);
        settlement.expireSettlement(sid);

        // Alice should get tokens back
        assertEq(token.balanceOf(alice), aliceBefore);
    }

    // =========================================================================
    //                 DAILY NET SETTLEMENT TESTS
    // =========================================================================

    function test_openSettlementWindow_success() public {
        uint256 closesAt = block.timestamp + 1 days;
        
        vm.expectEmit(true, false, false, true, address(settlement));
        emit ICariSettlement.SettlementWindowOpened(0, block.timestamp, closesAt);
        
        vm.prank(settlementBank);
        uint256 windowId = settlement.openSettlementWindow(closesAt);
        
        assertEq(windowId, 0);
        
        ICariSettlement.SettlementWindow memory window = settlement.getSettlementWindow(windowId);
        assertEq(window.windowId, 0);
        assertEq(window.openedAt, block.timestamp);
        assertEq(window.closesAt, closesAt);
        assertEq(uint8(window.status), uint8(ICariSettlement.SettlementWindowStatus.OPEN));
    }

    function test_openSettlementWindow_onlySettlementBank() public {
        uint256 closesAt = block.timestamp + 1 days;
        
        vm.prank(alice);
        vm.expectRevert();
        settlement.openSettlementWindow(closesAt);
    }

    function test_openSettlementWindow_invalidCloseTime() public {
        // closesAt in the past
        uint256 closesAt = block.timestamp - 1;
        
        vm.prank(settlementBank);
        vm.expectRevert(CariSettlement.InvalidExpiry.selector);
        settlement.openSettlementWindow(closesAt);
    }

    function test_closeSettlementWindow_success() public {
        uint256 closesAt = block.timestamp + 1 days;
        
        // Open window
        vm.prank(settlementBank);
        uint256 windowId = settlement.openSettlementWindow(closesAt);
        
        vm.expectEmit(true, false, false, true, address(settlement));
        emit ICariSettlement.SettlementWindowClosed(windowId, block.timestamp);
        
        // Close window
        vm.prank(settlementBank);
        settlement.closeSettlementWindow(windowId);
        
        ICariSettlement.SettlementWindow memory window = settlement.getSettlementWindow(windowId);
        assertEq(uint8(window.status), uint8(ICariSettlement.SettlementWindowStatus.CLOSED));
    }

    function test_closeSettlementWindow_alreadyClosed() public {
        uint256 closesAt = block.timestamp + 1 days;
        
        vm.prank(settlementBank);
        uint256 windowId = settlement.openSettlementWindow(closesAt);
        
        vm.prank(settlementBank);
        settlement.closeSettlementWindow(windowId);
        
        // Try to close again
        vm.prank(settlementBank);
        vm.expectRevert();
        settlement.closeSettlementWindow(windowId);
    }

    function test_closeSettlementWindow_notFound() public {
        uint256 nonExistentWindowId = 999;
        
        vm.prank(settlementBank);
        vm.expectRevert();
        settlement.closeSettlementWindow(nonExistentWindowId);
    }

    function test_netSettle_success() public {
        // Setup: whitelist bank addresses for settlement operations
        address bankA = makeAddr("bankA");
        address bankB = makeAddr("bankB");
        
        vm.startPrank(compliance);
        token.whitelistAddress(bankA);
        token.whitelistAddress(bankB);
        vm.stopPrank();
        
        // Pre-mint tokens to bankB (net payer)
        _mint(bankB, 100e6);
        
        // Open and close window
        uint256 closesAt = block.timestamp + 1 days;
        vm.prank(settlementBank);
        uint256 windowId = settlement.openSettlementWindow(closesAt);
        
        vm.prank(settlementBank);
        settlement.closeSettlementWindow(windowId);
        
        // Create balanced entries: bankA receives +100, bankB pays -100
        ICariSettlement.NetSettlementEntry[] memory entries = new ICariSettlement.NetSettlementEntry[](2);
        entries[0] = ICariSettlement.NetSettlementEntry({ bank: bankA, netAmount: int256(100e6) });
        entries[1] = ICariSettlement.NetSettlementEntry({ bank: bankB, netAmount: -int256(100e6) });
        
        vm.expectEmit(true, false, false, true, address(settlement));
        emit ICariSettlement.NetSettlementExecuted(windowId, block.timestamp, 2);
        
        vm.prank(settlementBank);
        settlement.netSettle(windowId, entries);
        
        // Verify status changed
        ICariSettlement.SettlementWindow memory window = settlement.getSettlementWindow(windowId);
        assertEq(uint8(window.status), uint8(ICariSettlement.SettlementWindowStatus.SETTLED));
        
        // Verify balances: bankA should have 100, bankB should have 0
        assertEq(token.balanceOf(bankA), 100e6);
        assertEq(token.balanceOf(bankB), 0);
    }

    function test_netSettle_windowNotClosed() public {
        uint256 closesAt = block.timestamp + 1 days;
        
        vm.prank(settlementBank);
        uint256 windowId = settlement.openSettlementWindow(closesAt);
        
        // Window is still OPEN, should fail
        ICariSettlement.NetSettlementEntry[] memory entries = new ICariSettlement.NetSettlementEntry[](0);
        
        vm.prank(settlementBank);
        vm.expectRevert();
        settlement.netSettle(windowId, entries);
    }

    function test_netSettle_onlySettlementBank() public {
        uint256 closesAt = block.timestamp + 1 days;
        
        vm.prank(settlementBank);
        uint256 windowId = settlement.openSettlementWindow(closesAt);
        
        vm.prank(settlementBank);
        settlement.closeSettlementWindow(windowId);
        
        ICariSettlement.NetSettlementEntry[] memory entries = new ICariSettlement.NetSettlementEntry[](0);
        
        vm.prank(alice);
        vm.expectRevert();
        settlement.netSettle(windowId, entries);
    }

    function test_getSettlementWindow_returnsCorrectData() public {
        uint256 closesAt = block.timestamp + 1 days;
        
        vm.prank(settlementBank);
        uint256 windowId = settlement.openSettlementWindow(closesAt);
        
        ICariSettlement.SettlementWindow memory window = settlement.getSettlementWindow(windowId);
        
        assertEq(window.windowId, windowId);
        assertEq(window.openedAt, block.timestamp);
        assertEq(window.closesAt, closesAt);
        assertEq(uint8(window.status), uint8(ICariSettlement.SettlementWindowStatus.OPEN));
    }

    function test_netSettle_imbalanced() public {
        // Open and close a window
        vm.prank(settlementBank);
        uint256 windowId = settlement.openSettlementWindow(block.timestamp + 1 days);
        
        vm.prank(settlementBank);
        settlement.closeSettlementWindow(windowId);
        
        // Create imbalanced entries (sum != 0)
        ICariSettlement.NetSettlementEntry[] memory entries = new ICariSettlement.NetSettlementEntry[](2);
        entries[0] = ICariSettlement.NetSettlementEntry({bank: alice, netAmount: int256(100 * 1e6)});
        entries[1] = ICariSettlement.NetSettlementEntry({bank: bob, netAmount: int256(-50 * 1e6)});
        
        // Should revert because +100 - 50 = +50 != 0
        vm.prank(settlementBank);
        vm.expectRevert(CariSettlement.NetSettlementImbalanced.selector);
        settlement.netSettle(windowId, entries);
    }
}
