// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import "./TestHelper.sol";
import "../contracts/interfaces/IMTokenizedDeposit.sol";

/**
 * @title MTokenizedDepositTest
 * @notice Unit tests for M&T Bank's tokenized deposit contract on Cari Network / ZKsync Prividium.
 */
contract MTokenizedDepositTest is TestHelper {
    // =========================================================================
    //                          INITIALIZATION
    // =========================================================================

    function test_initialize_name() public view {
        assertEq(token.name(), "M&T Bank Tokenized Deposit (Cari)");
    }

    function test_initialize_symbol() public view {
        assertEq(token.symbol(), "mtUSD");
    }

    function test_initialize_decimals() public view {
        assertEq(token.decimals(), 6);
    }

    function test_initialize_travelRuleThreshold() public view {
        assertEq(token.travelRuleThreshold(), 3_000 * 1e6);
    }

    function test_initialize_reserveOracle() public view {
        assertEq(address(token.reserveOracle()), address(oracle));
    }

    function test_initialize_adminHasRoles() public view {
        assertTrue(token.hasRole(token.DEFAULT_ADMIN_ROLE(), admin));
        assertTrue(token.hasRole(token.UPGRADER_ROLE(), admin));
        assertTrue(token.hasRole(token.PAUSER_ROLE(), admin));
    }

    function test_initialize_revertZeroAdmin() public {
        MTokenizedDeposit impl = new MTokenizedDeposit();
        vm.expectRevert(MTokenizedDeposit.ZeroAddress.selector);
        new ERC1967Proxy(
            address(impl),
            abi.encodeCall(MTokenizedDeposit.initialize, (address(0), address(oracle)))
        );
    }

    // =========================================================================
    //                              MINT
    // =========================================================================

    function test_mint_success() public {
        _mint(alice, 1000e6);
        assertEq(token.balanceOf(alice), 1000e6);
        assertEq(token.totalSupply(), 1000e6);
    }

    function test_mint_emitsEvent() public {
        vm.expectEmit(true, false, false, true, address(token));
        emit IMTokenizedDeposit.Mint(alice, 500e6, "ref-001");
        vm.prank(minter);
        token.mint(alice, 500e6, "ref-001");
    }

    function test_mint_revert_notMinter() public {
        vm.prank(alice);
        vm.expectRevert();
        token.mint(alice, 100e6, "ref");
    }

    function test_mint_revert_notWhitelisted() public {
        address outsider = makeAddr("outsider");
        vm.prank(minter);
        vm.expectRevert(abi.encodeWithSelector(MTokenizedDeposit.NotWhitelisted.selector, outsider));
        token.mint(outsider, 100e6, "ref");
    }

    function test_mint_revert_frozen() public {
        vm.prank(compliance);
        token.freezeAddress(alice);

        vm.prank(minter);
        vm.expectRevert(abi.encodeWithSelector(MTokenizedDeposit.AccountFrozen.selector, alice));
        token.mint(alice, 100e6, "ref");
    }

    function test_mint_revert_zeroAmount() public {
        vm.prank(minter);
        vm.expectRevert(MTokenizedDeposit.ZeroAmount.selector);
        token.mint(alice, 0, "ref");
    }

    function test_mint_revert_zeroAddress() public {
        vm.prank(minter);
        vm.expectRevert(MTokenizedDeposit.ZeroAddress.selector);
        token.mint(address(0), 100e6, "ref");
    }

    function test_mint_revert_exceedsReserves() public {
        // Try to mint more than total reserves ($10M)
        vm.prank(minter);
        vm.expectRevert(
            abi.encodeWithSelector(
                MTokenizedDeposit.ReserveBackingInsufficient.selector,
                INITIAL_RESERVES + 1,
                INITIAL_RESERVES
            )
        );
        token.mint(alice, INITIAL_RESERVES + 1, "ref");
    }

    function test_mint_revert_staleAttestation() public {
        // Warp past staleness threshold
        vm.warp(block.timestamp + MAX_STALENESS + 1);

        vm.prank(minter);
        vm.expectRevert();
        token.mint(alice, 100e6, "ref");
    }

    function test_mint_revert_whenPaused() public {
        vm.prank(pauser);
        token.pause();

        vm.prank(minter);
        vm.expectRevert();
        token.mint(alice, 100e6, "ref");
    }

    // =========================================================================
    //                              BURN
    // =========================================================================

    function test_burn_success() public {
        _mint(alice, 1000e6);

        _burn(alice, 400e6);
        assertEq(token.balanceOf(alice), 600e6);
        assertEq(token.totalSupply(), 600e6);
    }

    function test_burn_emitsEvent() public {
        _mint(alice, 1000e6);

        vm.expectEmit(true, false, false, true, address(token));
        emit IMTokenizedDeposit.Burn(alice, 500e6, "redeem-001");
        vm.prank(burner);
        token.burn(alice, 500e6, "redeem-001");
    }

    function test_burn_revert_notBurner() public {
        _mint(alice, 1000e6);
        vm.prank(alice);
        vm.expectRevert();
        token.burn(alice, 100e6, "ref");
    }

    function test_burn_revert_zeroAmount() public {
        vm.prank(burner);
        vm.expectRevert(MTokenizedDeposit.ZeroAmount.selector);
        token.burn(alice, 0, "ref");
    }

    function test_burn_revert_insufficientBalance() public {
        _mint(alice, 100e6);
        vm.prank(burner);
        vm.expectRevert(); // ERC20 underflow
        token.burn(alice, 200e6, "ref");
    }

    // =========================================================================
    //                          TRANSFER
    // =========================================================================

    function test_transfer_betweenWhitelisted() public {
        _mint(alice, 1000e6);

        vm.prank(alice);
        token.transfer(bob, 300e6);

        assertEq(token.balanceOf(alice), 700e6);
        assertEq(token.balanceOf(bob), 300e6);
    }

    function test_transfer_revert_senderNotWhitelisted() public {
        _mint(alice, 1000e6);

        // Remove alice from whitelist
        vm.prank(compliance);
        token.removeFromWhitelist(alice);

        vm.prank(alice);
        vm.expectRevert(abi.encodeWithSelector(MTokenizedDeposit.NotWhitelisted.selector, alice));
        token.transfer(bob, 100e6);
    }

    function test_transfer_revert_receiverNotWhitelisted() public {
        _mint(alice, 1000e6);
        address outsider = makeAddr("outsider");

        vm.prank(alice);
        vm.expectRevert(abi.encodeWithSelector(MTokenizedDeposit.NotWhitelisted.selector, outsider));
        token.transfer(outsider, 100e6);
    }

    function test_transfer_revert_senderFrozen() public {
        _mint(alice, 1000e6);

        vm.prank(compliance);
        token.freezeAddress(alice);

        vm.prank(alice);
        vm.expectRevert(abi.encodeWithSelector(MTokenizedDeposit.AccountFrozen.selector, alice));
        token.transfer(bob, 100e6);
    }

    function test_transfer_revert_receiverFrozen() public {
        _mint(alice, 1000e6);

        vm.prank(compliance);
        token.freezeAddress(bob);

        vm.prank(alice);
        vm.expectRevert(abi.encodeWithSelector(MTokenizedDeposit.AccountFrozen.selector, bob));
        token.transfer(bob, 100e6);
    }

    // =========================================================================
    //                        TRAVEL RULE
    // =========================================================================

    function test_transferWithTravelRule_success() public {
        _mint(alice, 5000e6);

        IMTokenizedDeposit.TravelRuleData memory td = IMTokenizedDeposit.TravelRuleData({
            originatorHash: keccak256("Alice PII"),
            beneficiaryHash: keccak256("Bob PII"),
            originatorInstitution: "M&T Bank",
            beneficiaryInstitution: "Cari Member Bank B"
        });

        vm.expectEmit(true, true, false, true, address(token));
        emit IMTokenizedDeposit.TravelRuleTransfer(
            alice, bob, 5000e6, td.originatorHash, td.beneficiaryHash
        );

        vm.prank(alice);
        bool ok = token.transferWithTravelRule(bob, 5000e6, td);
        assertTrue(ok);
        assertEq(token.balanceOf(bob), 5000e6);
    }

    // =========================================================================
    //                      COMPLIANCE CONTROLS
    // =========================================================================

    function test_whitelistAddress() public {
        address newAddr = makeAddr("newAddr");
        assertFalse(token.isWhitelisted(newAddr));

        vm.prank(compliance);
        token.whitelistAddress(newAddr);
        assertTrue(token.isWhitelisted(newAddr));
    }

    function test_removeFromWhitelist() public {
        assertTrue(token.isWhitelisted(alice));

        vm.prank(compliance);
        token.removeFromWhitelist(alice);
        assertFalse(token.isWhitelisted(alice));
    }

    function test_freezeAddress() public {
        assertFalse(token.isFrozen(alice));

        vm.prank(compliance);
        token.freezeAddress(alice);
        assertTrue(token.isFrozen(alice));
    }

    function test_unfreezeAddress() public {
        vm.prank(compliance);
        token.freezeAddress(alice);
        assertTrue(token.isFrozen(alice));

        vm.prank(compliance);
        token.unfreezeAddress(alice);
        assertFalse(token.isFrozen(alice));
    }

    function test_whitelist_revert_notCompliance() public {
        vm.prank(alice);
        vm.expectRevert();
        token.whitelistAddress(makeAddr("x"));
    }

    function test_freeze_revert_notCompliance() public {
        vm.prank(alice);
        vm.expectRevert();
        token.freezeAddress(alice);
    }

    // =========================================================================
    //                      FORCE TRANSFER
    // =========================================================================

    function test_forceTransfer_success() public {
        _mint(alice, 1000e6);

        // Freeze alice (OFAC hit)
        vm.prank(compliance);
        token.freezeAddress(alice);

        // Force transfer from frozen alice to escrow
        vm.prank(compliance);
        vm.recordLogs();
        token.forceTransfer(alice, escrow, 1000e6, "OFAC seizure order #12345");

        // Verify the ForcedTransfer event was emitted
        Vm.Log[] memory logs = vm.getRecordedLogs();
        bool foundEvent = false;
        bytes32 forcedTransferSig = keccak256("ForcedTransfer(address,address,uint256,string)");
        for (uint256 i = 0; i < logs.length; i++) {
            if (logs[i].topics[0] == forcedTransferSig) {
                foundEvent = true;
                break;
            }
        }
        assertTrue(foundEvent, "ForcedTransfer event not emitted");

        assertEq(token.balanceOf(alice), 0);
        assertEq(token.balanceOf(escrow), 1000e6);
    }

    function test_forceTransfer_revert_notCompliance() public {
        _mint(alice, 1000e6);
        vm.prank(alice);
        vm.expectRevert();
        token.forceTransfer(alice, bob, 100e6, "nope");
    }

    function test_forceTransfer_revert_zeroAmount() public {
        vm.prank(compliance);
        vm.expectRevert(MTokenizedDeposit.ZeroAmount.selector);
        token.forceTransfer(alice, bob, 0, "reason");
    }

    // =========================================================================
    //                          PAUSE
    // =========================================================================

    function test_pause_blocksMint() public {
        vm.prank(pauser);
        token.pause();

        vm.prank(minter);
        vm.expectRevert();
        token.mint(alice, 100e6, "ref");
    }

    function test_pause_blocksTransfer() public {
        _mint(alice, 1000e6);

        vm.prank(pauser);
        token.pause();

        vm.prank(alice);
        vm.expectRevert();
        token.transfer(bob, 100e6);
    }

    function test_unpause_restoresOperations() public {
        vm.prank(pauser);
        token.pause();

        vm.prank(pauser);
        token.unpause();

        _mint(alice, 100e6);
        assertEq(token.balanceOf(alice), 100e6);
    }

    function test_pause_revert_notPauser() public {
        vm.prank(alice);
        vm.expectRevert();
        token.pause();
    }

    // =========================================================================
    //                      ADMIN CONFIG
    // =========================================================================

    function test_setReserveOracle() public {
        address newOracle = makeAddr("newOracle");
        vm.prank(admin);
        token.setReserveOracle(newOracle);
        assertEq(address(token.reserveOracle()), newOracle);
    }

    function test_setReserveOracle_revert_zeroAddress() public {
        vm.prank(admin);
        vm.expectRevert(MTokenizedDeposit.ZeroAddress.selector);
        token.setReserveOracle(address(0));
    }

    function test_setReserveOracle_revert_notAdmin() public {
        vm.prank(alice);
        vm.expectRevert();
        token.setReserveOracle(makeAddr("x"));
    }

    function test_setCariSettlement() public {
        address newSettlement = makeAddr("newSettlement");
        vm.prank(admin);
        token.setCariSettlement(newSettlement);
        assertEq(token.cariSettlement(), newSettlement);
        assertTrue(token.hasRole(token.SETTLEMENT_ROLE(), newSettlement));
    }

    function test_setTravelRuleThreshold() public {
        vm.prank(admin);
        token.setTravelRuleThreshold(5000e6);
        assertEq(token.travelRuleThreshold(), 5000e6);
    }

    // =========================================================================
    //                   SETTLEMENT CALLBACKS
    // =========================================================================

    function test_settlementMint_success() public {
        vm.prank(address(settlement));
        token.settlementMint(alice, 500e6, keccak256("settle-1"));
        assertEq(token.balanceOf(alice), 500e6);
    }

    function test_settlementBurn_success() public {
        _mint(alice, 1000e6);
        vm.prank(address(settlement));
        token.settlementBurn(alice, 400e6, keccak256("settle-2"));
        assertEq(token.balanceOf(alice), 600e6);
    }

    function test_settlementMint_revert_notSettlementRole() public {
        vm.prank(alice);
        vm.expectRevert();
        token.settlementMint(alice, 100e6, keccak256("bad"));
    }

    function test_settlementBurn_revert_notSettlementRole() public {
        vm.prank(alice);
        vm.expectRevert();
        token.settlementBurn(alice, 100e6, keccak256("bad"));
    }

    // =========================================================================
    //                   SETTLEMENT RETURN (FINDING-001)
    // =========================================================================

    function test_settlementReturn_success() public {
        bytes32 settlementId = keccak256("settle-return-1");
        
        vm.expectEmit(true, true, false, true, address(token));
        emit IMTokenizedDeposit.SettlementReturn(alice, 500e6, settlementId);
        
        vm.prank(address(settlement));
        token.settlementReturn(alice, 500e6, settlementId);
        
        assertEq(token.balanceOf(alice), 500e6);
    }

    function test_settlementReturn_bypassesReserveCheck() public {
        // First, mint tokens to alice up to the reserve limit
        _mint(alice, INITIAL_RESERVES);
        assertEq(token.totalSupply(), INITIAL_RESERVES);
        
        // Now reduce reserves below current supply
        vm.prank(attestor);
        oracle.updateAttestation(INITIAL_RESERVES / 2, keccak256("reduced"));
        
        // settlementMint should fail due to insufficient reserves
        vm.prank(address(settlement));
        vm.expectRevert();
        token.settlementMint(bob, 100e6, keccak256("settle-mint"));
        
        // But settlementReturn should succeed (bypasses reserve check)
        bytes32 settlementId = keccak256("settle-return-2");
        vm.prank(address(settlement));
        token.settlementReturn(bob, 100e6, settlementId);
        
        assertEq(token.balanceOf(bob), 100e6);
    }

    function test_settlementReturn_onlySettlementRole() public {
        vm.prank(alice);
        vm.expectRevert();
        token.settlementReturn(alice, 100e6, keccak256("bad"));
        
        vm.prank(minter);
        vm.expectRevert();
        token.settlementReturn(alice, 100e6, keccak256("bad"));
        
        vm.prank(burner);
        vm.expectRevert();
        token.settlementReturn(alice, 100e6, keccak256("bad"));
    }

    function test_settlementReturn_rejectsZeroAddress() public {
        vm.prank(address(settlement));
        vm.expectRevert(MTokenizedDeposit.ZeroAddress.selector);
        token.settlementReturn(address(0), 100e6, keccak256("bad"));
    }

    function test_settlementReturn_rejectsZeroAmount() public {
        vm.prank(address(settlement));
        vm.expectRevert(MTokenizedDeposit.ZeroAmount.selector);
        token.settlementReturn(alice, 0, keccak256("bad"));
    }

    function test_settlementReturn_whenPaused_reverts() public {
        vm.prank(pauser);
        token.pause();
        
        vm.prank(address(settlement));
        vm.expectRevert();
        token.settlementReturn(alice, 100e6, keccak256("bad"));
    }

    // =========================================================================
    //                      OPERATOR ROLE TESTS
    // =========================================================================

    function test_setOperator_success() public {
        address newOperator = makeAddr("newOperator");
        
        vm.expectEmit(true, true, false, false, address(token));
        emit IMTokenizedDeposit.OperatorUpdated(address(0), newOperator);
        
        vm.prank(admin);
        token.setOperator(newOperator);
        
        assertEq(token.operator(), newOperator);
    }

    function test_setOperator_grantsRoles() public {
        address newOperator = makeAddr("newOperator");
        
        vm.prank(admin);
        token.setOperator(newOperator);
        
        assertTrue(token.hasRole(token.MINTER_ROLE(), newOperator));
        assertTrue(token.hasRole(token.BURNER_ROLE(), newOperator));
        assertTrue(token.hasRole(token.OPERATOR_ROLE(), newOperator));
    }

    function test_setOperator_revokesOldOperator() public {
        address firstOperator = makeAddr("firstOperator");
        address secondOperator = makeAddr("secondOperator");
        
        // Set first operator
        vm.prank(admin);
        token.setOperator(firstOperator);
        
        assertTrue(token.hasRole(token.MINTER_ROLE(), firstOperator));
        assertTrue(token.hasRole(token.BURNER_ROLE(), firstOperator));
        assertTrue(token.hasRole(token.OPERATOR_ROLE(), firstOperator));
        
        // Set second operator - first should lose roles
        vm.prank(admin);
        token.setOperator(secondOperator);
        
        // First operator loses roles
        assertFalse(token.hasRole(token.MINTER_ROLE(), firstOperator));
        assertFalse(token.hasRole(token.BURNER_ROLE(), firstOperator));
        assertFalse(token.hasRole(token.OPERATOR_ROLE(), firstOperator));
        
        // Second operator has roles
        assertTrue(token.hasRole(token.MINTER_ROLE(), secondOperator));
        assertTrue(token.hasRole(token.BURNER_ROLE(), secondOperator));
        assertTrue(token.hasRole(token.OPERATOR_ROLE(), secondOperator));
        
        assertEq(token.operator(), secondOperator);
    }

    function test_setOperator_onlyAdmin() public {
        address newOperator = makeAddr("newOperator");
        
        vm.prank(alice);
        vm.expectRevert();
        token.setOperator(newOperator);
        
        // Verify operator was not set
        assertEq(token.operator(), address(0));
    }

    function test_setOperator_rejectsZeroAddress() public {
        vm.prank(admin);
        vm.expectRevert(MTokenizedDeposit.ZeroAddress.selector);
        token.setOperator(address(0));
    }

    function test_operator_canMint() public {
        address operatorAddr = makeAddr("operatorAddr");
        
        // Set operator
        vm.prank(admin);
        token.setOperator(operatorAddr);
        
        // Whitelist operatorAddr recipient for minting
        vm.prank(compliance);
        token.whitelistAddress(operatorAddr);
        
        // Operator mints tokens
        vm.prank(operatorAddr);
        token.mint(alice, 1000e6, "operator-mint-ref");
        
        assertEq(token.balanceOf(alice), 1000e6);
    }

    function test_operator_canBurn() public {
        address operatorAddr = makeAddr("operatorAddr");
        
        // Set operator
        vm.prank(admin);
        token.setOperator(operatorAddr);
        
        // First mint some tokens to alice via existing minter
        _mint(alice, 1000e6);
        assertEq(token.balanceOf(alice), 1000e6);
        
        // Operator burns tokens
        vm.prank(operatorAddr);
        token.burn(alice, 500e6, "operator-burn-ref");
        
        assertEq(token.balanceOf(alice), 500e6);
    }
}
