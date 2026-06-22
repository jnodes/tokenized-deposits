// SPDX-License-Identifier: MIT
pragma solidity ^0.8.26;

import "forge-std/Test.sol";
import "@openzeppelin/contracts/proxy/ERC1967/ERC1967Proxy.sol";
import "../contracts/TokenizedDeposit.sol";
import "../contracts/ReserveOracle.sol";
import "../contracts/CariSettlement.sol";

/**
 * @title TestHelper
 * @notice Shared setup for all StableArch Council contract tests.
 *         Deploys proxied instances of ReserveOracle, TokenizedDeposit, and CariSettlement
 *         with standard roles assigned.
 */
abstract contract TestHelper is Test {
    // --- Contracts ---
    TokenizedDeposit public token;
    ReserveOracle public oracle;
    CariSettlement public settlement;

    // --- Actors ---
    address public admin = makeAddr("admin");
    address public minter = makeAddr("minter");
    address public burner = makeAddr("burner");
    address public compliance = makeAddr("compliance");
    address public pauser = makeAddr("pauser");
    address public attestor = makeAddr("attestor");
    address public settlementOperator = makeAddr("settlementOperator");
    address public initiator = makeAddr("initiator");

    address public alice = makeAddr("alice");
    address public bob = makeAddr("bob");
    address public charlie = makeAddr("charlie");
    address public escrow = makeAddr("escrow");

    address public memberBankB = makeAddr("memberBankB");
    address public settlementBank = makeAddr("settlementBank");

    // --- Constants ---
    uint256 public constant INITIAL_RESERVES = 10_000_000 * 1e6; // $10M
    uint256 public constant MAX_STALENESS = 86_400; // 24 hours
    uint256 public constant SETTLEMENT_EXPIRY = 86_400; // 24 hours
    bytes32 public constant ATTEST_HASH = keccak256("reserve-report-2026-Q1");

    function setUp() public virtual {
        vm.startPrank(admin);

        // --- Deploy ReserveOracle behind proxy ---
        ReserveOracle oracleImpl = new ReserveOracle();
        bytes memory oracleInit = abi.encodeCall(
            ReserveOracle.initialize,
            (admin, attestor, MAX_STALENESS)
        );
        oracle = ReserveOracle(address(new ERC1967Proxy(address(oracleImpl), oracleInit)));

        // --- Deploy TokenizedDeposit behind proxy ---
        TokenizedDeposit tokenImpl = new TokenizedDeposit();
        bytes memory tokenInit = abi.encodeCall(
            TokenizedDeposit.initialize,
            (admin, address(oracle))
        );
        token = TokenizedDeposit(address(new ERC1967Proxy(address(tokenImpl), tokenInit)));

        // --- Deploy CariSettlement behind proxy ---
        CariSettlement settlementImpl = new CariSettlement();
        bytes memory settlementInit = abi.encodeCall(
            CariSettlement.initialize,
            (admin, address(token), SETTLEMENT_EXPIRY)
        );
        settlement = CariSettlement(address(new ERC1967Proxy(address(settlementImpl), settlementInit)));

        // --- Assign roles on token ---
        token.grantRole(token.MINTER_ROLE(), minter);
        token.grantRole(token.BURNER_ROLE(), burner);
        token.grantRole(token.COMPLIANCE_ROLE(), compliance);
        token.grantRole(token.PAUSER_ROLE(), pauser);

        // --- Link settlement to token ---
        token.setCariSettlement(address(settlement));

        // --- Assign roles on settlement ---
        settlement.grantRole(settlement.SETTLEMENT_OPERATOR_ROLE(), settlementOperator);
        settlement.grantRole(settlement.INITIATOR_ROLE(), initiator);
        settlement.addMemberBank(memberBankB);
        settlement.grantRole(settlement.SETTLEMENT_BANK_ROLE(), settlementBank);

        // --- Seed oracle with initial reserves ---
        vm.stopPrank();
        vm.prank(attestor);
        oracle.updateAttestation(INITIAL_RESERVES, ATTEST_HASH);

        // --- Whitelist standard test accounts ---
        vm.startPrank(compliance);
        token.whitelistAddress(alice);
        token.whitelistAddress(bob);
        token.whitelistAddress(charlie);
        token.whitelistAddress(escrow);
        vm.stopPrank();
    }

    // --- Helpers ---

    /// @dev Mint `amount` tokens to `to` via the minter role.
    function _mint(address to, uint256 amount) internal {
        vm.prank(minter);
        token.mint(to, amount, "test-ref");
    }

    /// @dev Burn `amount` tokens from `from` via the burner role.
    function _burn(address from, uint256 amount) internal {
        vm.prank(burner);
        token.burn(from, amount, "test-ref");
    }
}
