"""测试辅助：给测试用户加 email_verified_at，跳过 V2-F.3 邮箱验证流程。

测试场景下不验证 SMTP 邮件流，直接 mark_email_verified 让用户能 /chat。
"""
from app.auth.repository import mark_email_verified


async def verify_user_email(db, user):
    """测试辅助：直接 mark user 为已验证邮箱。"""
    return await mark_email_verified(db, user)
