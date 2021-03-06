"""Add known_city_map.

Revision ID: edf7c598cec7
Revises: 7df9f77009a6
Create Date: 2021-02-05 16:42:45.175313

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'edf7c598cec7'
down_revision = '7df9f77009a6'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('known_city_map',
    sa.Column('subscription_id', sa.Integer(), nullable=False),
    sa.Column('city_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['city_id'], ['vaccination_city.id'], ),
    sa.ForeignKeyConstraint(['subscription_id'], ['spot_subscription.id'], ),
    sa.PrimaryKeyConstraint('subscription_id', 'city_id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('known_city_map')
    # ### end Alembic commands ###
