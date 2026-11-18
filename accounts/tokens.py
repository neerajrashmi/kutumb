# apps/accounts/tokens.py
from django.core import signing
from django.utils import timezone
from genealogy.models import IndividualDetail
from accounts.models import UserDetail

TOKEN_SALT = 'family-tree-invitation-token-salt'
TOKEN_MAX_AGE_SECONDS = 7 * 24 * 60 * 60  # 7 days validity


class InvitationTokenService:
    @classmethod
    def generate_token(cls, individual_id: str, host_user_id: str) -> str:
        """
        Creates a timestamped, signed token containing individual and host user IDs.
        """
        payload = {
            'individual_id': individual_id,
            'host_user_id': host_user_id,
        }
        return signing.dumps(payload, salt=TOKEN_SALT)

    @classmethod
    def validate_token(cls, token: str):
        """
        Validates token signature, expiration (7 days), and confirms that:
        1. The target Individual exists.
        2. The target Individual does NOT already have an active UserDetail account.
        Returns (individual, host_user) tuple or raises ValidationError.
        """
        try:
            payload = signing.loads(token, salt=TOKEN_SALT, max_age=TOKEN_MAX_AGE_SECONDS)
        except signing.SignatureExpired:
            raise ValueError("This invitation link has expired (validity is 7 days). Please request a new invitation.")
        except signing.BadSignature:
            raise ValueError("Invalid invitation link. The token could not be verified.")

        ind_id = payload.get('individual_id')
        host_id = payload.get('host_user_id')

        individual = IndividualDetail.objects.filter(pk=ind_id).first()
        if not individual:
            raise ValueError("The family member associated with this invitation was not found.")

        # SRS Rule 7.1: Verify user account does not already exist
        if UserDetail.objects.filter(pk=ind_id).exists():
            raise ValueError("An account has already been registered and activated for this family member.")

        host_user = UserDetail.objects.filter(pk=host_id).first()
        return individual, host_user