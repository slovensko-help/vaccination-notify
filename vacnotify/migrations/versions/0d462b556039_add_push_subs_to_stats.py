"""Add push subs to stats.

Revision ID: 0d462b556039
Revises: a6464386756e
Create Date: 2021-02-15 23:55:56.527447

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0d462b556039'
down_revision = 'a6464386756e'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('subscription_stats', sa.Column('shared_push_subs', sa.Integer(), nullable=True))
    op.add_column('subscription_stats', sa.Column('unique_push_subs', sa.Integer(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('subscription_stats', 'unique_push_subs')
    op.drop_column('subscription_stats', 'shared_push_subs')
    # ### end Alembic commands ###
