// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import "./TestHelper.sol";

/**
 * @title ReserveOracleTest
 * @notice Unit tests for the 1:1 reserve backing oracle.
 *         M&T Bank | Cari Network | ZKsync Prividium.
 */
contract ReserveOracleTest is TestHelper {
    // =========================================================================
    //                          INITIALIZATION
    // =========================================================================

    function test_initialize_maxStaleness() public view {
        assertEq(oracle.maxStaleness(), MAX_STALENESS);
    }

    function test_initialize_roles() public view {
        assertTrue(oracle.hasRole(oracle.DEFAULT_ADMIN_ROLE(), admin));
        assertTrue(oracle.hasRole(oracle.ATTESTOR_ROLE(), attestor));
        assertTrue(oracle.hasRole(oracle.UPGRADER_ROLE(), admin));
        assertTrue(oracle.hasRole(oracle.PAUSER_ROLE(), admin));
    }

    function test_initialize_revert_zeroStaleness() public {
        ReserveOracle impl = new ReserveOracle();
        vm.expectRevert(ReserveOracle.InvalidStaleness.selector);
        new ERC1967Proxy(
            address(impl),
            abi.encodeCall(ReserveOracle.initialize, (admin, attestor, 0))
        );
    }

    // =========================================================================
    //                        ATTESTATION
    // =========================================================================

    function test_updateAttestation_success() public {
        uint256 newReserves = 20_000_000e6;
        bytes32 hash = keccak256("Q2-report");

        vm.prank(attestor);
        oracle.updateAttestation(newReserves, hash);

        assertEq(oracle.totalReserves(), newReserves);
        assertEq(oracle.attestationHash(), hash);
        assertEq(oracle.lastAttestedAt(), block.timestamp);
    }

    function test_updateAttestation_emitsEvent() public {
        uint256 newReserves = 5_000_000e6;
        bytes32 hash = keccak256("report");

        vm.expectEmit(false, false, false, true, address(oracle));
        emit IReserveOracle.ReserveAttestationUpdated(newReserves, block.timestamp, hash);

        vm.prank(attestor);
        oracle.updateAttestation(newReserves, hash);
    }

    function test_updateAttestation_revert_notAttestor() public {
        vm.prank(alice);
        vm.expectRevert();
        oracle.updateAttestation(1e6, keccak256("x"));
    }

    function test_updateAttestation_revert_zeroReserves() public {
        vm.prank(attestor);
        vm.expectRevert(ReserveOracle.ZeroReserves.selector);
        oracle.updateAttestation(0, keccak256("x"));
    }

    function test_updateAttestation_revert_whenPaused() public {
        vm.prank(admin);
        oracle.pause();

        vm.prank(attestor);
        vm.expectRevert();
        oracle.updateAttestation(1e6, keccak256("x"));
    }

    // =========================================================================
    //                          canMint
    // =========================================================================

    function test_canMint_withinReserves() public view {
        assertTrue(oracle.canMint(0, INITIAL_RESERVES));
        assertTrue(oracle.canMint(INITIAL_RESERVES - 1, 1));
    }

    function test_canMint_exceedsReserves() public view {
        assertFalse(oracle.canMint(0, INITIAL_RESERVES + 1));
        assertFalse(oracle.canMint(INITIAL_RESERVES, 1));
    }

    function test_canMint_staleAttestation() public {
        vm.warp(block.timestamp + MAX_STALENESS + 1);
        assertFalse(oracle.canMint(0, 1));
    }

    function test_canMint_freshAfterUpdate() public {
        vm.warp(block.timestamp + MAX_STALENESS + 1);
        assertFalse(oracle.canMint(0, 1));

        // Refresh attestation
        vm.prank(attestor);
        oracle.updateAttestation(INITIAL_RESERVES, ATTEST_HASH);

        assertTrue(oracle.canMint(0, 1));
    }

    // =========================================================================
    //                      STALENESS
    // =========================================================================

    function test_isAttestationFresh_true() public view {
        assertTrue(oracle.isAttestationFresh());
    }

    function test_isAttestationFresh_false_afterExpiry() public {
        vm.warp(block.timestamp + MAX_STALENESS + 1);
        assertFalse(oracle.isAttestationFresh());
    }

    function test_isAttestationFresh_false_noAttestation() public {
        // Deploy a fresh oracle with no attestation
        ReserveOracle impl = new ReserveOracle();
        ReserveOracle fresh = ReserveOracle(address(new ERC1967Proxy(
            address(impl),
            abi.encodeCall(ReserveOracle.initialize, (admin, attestor, MAX_STALENESS))
        )));
        assertFalse(fresh.isAttestationFresh());
    }

    // =========================================================================
    //                      ADMIN CONFIG
    // =========================================================================

    function test_setMaxStaleness() public {
        vm.prank(admin);
        oracle.setMaxStaleness(3600);
        assertEq(oracle.maxStaleness(), 3600);
    }

    function test_setMaxStaleness_revert_zero() public {
        vm.prank(admin);
        vm.expectRevert(ReserveOracle.InvalidStaleness.selector);
        oracle.setMaxStaleness(0);
    }

    function test_setMaxStaleness_revert_notAdmin() public {
        vm.prank(alice);
        vm.expectRevert();
        oracle.setMaxStaleness(3600);
    }

    // =========================================================================
    //                          PAUSE
    // =========================================================================

    function test_pause_blocksAttestation() public {
        vm.prank(admin);
        oracle.pause();

        vm.prank(attestor);
        vm.expectRevert();
        oracle.updateAttestation(1e6, keccak256("x"));
    }

    function test_unpause_restoresAttestation() public {
        vm.prank(admin);
        oracle.pause();

        vm.prank(admin);
        oracle.unpause();

        vm.prank(attestor);
        oracle.updateAttestation(1e6, keccak256("x"));
        assertEq(oracle.totalReserves(), 1e6);
    }

    // =========================================================================
    //                  CHECK STALENESS (FINDING-002)
    // =========================================================================

    function test_checkStaleness_fresh() public {
        // Right after attestation in setUp, should be fresh
        (bool isFresh, uint256 secondsUntilStale) = oracle.checkStaleness();
        
        assertTrue(isFresh);
        assertEq(secondsUntilStale, MAX_STALENESS); // Full time remaining
    }

    function test_checkStaleness_warning() public {
        // Warp to 80% of maxStaleness (past the 75% warning threshold)
        uint256 warningThreshold = (MAX_STALENESS * 75) / 100;
        uint256 elapsed = warningThreshold + (MAX_STALENESS / 10); // 85% of max
        vm.warp(block.timestamp + elapsed);
        
        // Expect the warning event
        vm.expectEmit(false, false, false, true, address(oracle));
        emit IReserveOracle.AttestationStalenessWarning(
            oracle.lastAttestedAt(),
            MAX_STALENESS,
            block.timestamp
        );
        
        (bool isFresh, uint256 secondsUntilStale) = oracle.checkStaleness();
        
        assertTrue(isFresh); // Still fresh, just warning
        assertEq(secondsUntilStale, MAX_STALENESS - elapsed);
    }

    function test_checkStaleness_stale() public {
        // Warp past maxStaleness
        vm.warp(block.timestamp + MAX_STALENESS + 1);
        
        // Expect the stale event
        vm.expectEmit(false, false, false, true, address(oracle));
        emit IReserveOracle.AttestationStale(
            oracle.lastAttestedAt(),
            MAX_STALENESS,
            block.timestamp
        );
        
        (bool isFresh, uint256 secondsUntilStale) = oracle.checkStaleness();
        
        assertFalse(isFresh);
        assertEq(secondsUntilStale, 0);
    }

    function test_stalenessWarningThresholdSeconds() public view {
        uint256 expected = (MAX_STALENESS * 75) / 100;
        assertEq(oracle.stalenessWarningThresholdSeconds(), expected);
    }

    function test_checkStaleness_atExactWarningThreshold() public {
        // Warp to exactly 75% of maxStaleness
        uint256 warningThreshold = (MAX_STALENESS * 75) / 100;
        vm.warp(block.timestamp + warningThreshold);
        
        // At exactly the threshold, should NOT emit warning yet (need to be past it)
        (bool isFresh, uint256 secondsUntilStale) = oracle.checkStaleness();
        
        assertTrue(isFresh);
        assertEq(secondsUntilStale, MAX_STALENESS - warningThreshold);
    }

    function test_checkStaleness_justPastWarningThreshold() public {
        // Warp to just past 75% of maxStaleness
        uint256 warningThreshold = (MAX_STALENESS * 75) / 100;
        vm.warp(block.timestamp + warningThreshold + 1);
        
        // Expect the warning event
        vm.expectEmit(false, false, false, true, address(oracle));
        emit IReserveOracle.AttestationStalenessWarning(
            oracle.lastAttestedAt(),
            MAX_STALENESS,
            block.timestamp
        );
        
        (bool isFresh, uint256 secondsUntilStale) = oracle.checkStaleness();
        
        assertTrue(isFresh);
        assertEq(secondsUntilStale, MAX_STALENESS - warningThreshold - 1);
    }

    function test_checkStaleness_noAttestation() public {
        // Deploy a fresh oracle with no attestation
        ReserveOracle impl = new ReserveOracle();
        ReserveOracle fresh = ReserveOracle(address(new ERC1967Proxy(
            address(impl),
            abi.encodeCall(ReserveOracle.initialize, (admin, attestor, MAX_STALENESS))
        )));
        
        // Expect stale event with lastAttestedAt = 0
        vm.expectEmit(false, false, false, true, address(fresh));
        emit IReserveOracle.AttestationStale(0, MAX_STALENESS, block.timestamp);
        
        (bool isFresh, uint256 secondsUntilStale) = fresh.checkStaleness();
        
        assertFalse(isFresh);
        assertEq(secondsUntilStale, 0);
    }

    function test_STALENESS_WARNING_PCT_constant() public view {
        assertEq(oracle.STALENESS_WARNING_PCT(), 75);
    }
}
