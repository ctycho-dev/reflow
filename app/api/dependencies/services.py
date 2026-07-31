from app.domain.transfer.service import TransferService
from app.domain.transfer.repo import TransferRepository
from app.domain.stats.service import StatsService
from app.domain.stats.repo import StatsRepository
from app.domain.token.repo import TokenRepository
from app.domain.token.service import TokenService
from app.domain.contract.repo import ContractRepository
from app.domain.contract.service import ContractService
from app.domain.campaign.service import CampaignService
from app.domain.campaign.repo import CampaignRepository
from app.domain.wallet.repo import WalletRepository
from app.domain.enrollment.repo import EnrollmentRepository
from app.domain.enrollment.service import EnrollmentService
from app.domain.auth.repo import AuthRepository
from app.domain.auth.service import AuthService
from app.domain.campaign.finalizer_repo import FinalizerRepository
from app.domain.campaign.finalizer_service import FinalizerService
from app.domain.campaign.reward_service import RewardService
from app.domain.campaign.reward_repo import RewardClaimRepository


def get_token_service() -> TokenService:
    return TokenService(repo=TokenRepository())


def get_contract_service() -> ContractService:
    return ContractService(repo=ContractRepository())


def get_transfer_service() -> TransferService:
    return TransferService(repo=TransferRepository())


def get_stats_service() -> StatsService:
    return StatsService(repo=StatsRepository())


def get_campaign_service() -> CampaignService:
    return CampaignService(
        repo=CampaignRepository(),
        token_repo=TokenRepository(),
        contract_repo=ContractRepository()
    )


def get_enrollment_service() -> EnrollmentService:
    return EnrollmentService(
        repo=EnrollmentRepository(),
        campaign_repo=CampaignRepository(),
        wallet_repo=WalletRepository(),
        transfer_repo=TransferRepository(),
    )


def get_auth_service() -> AuthService:
    """Stateless service with stateless repos."""
    return AuthService(
        repo=AuthRepository(),
        wallet_repo=WalletRepository(),
    )


def get_finalizer_service() -> FinalizerService:
    return FinalizerService(FinalizerRepository())


def get_reward_service() -> RewardService:
    return RewardService(RewardClaimRepository())
