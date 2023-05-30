from re import A
import brownie
import pytest
import time

from brownie.network.account import Account

from brownie import (
    interface,
    RainProduct,
)

from scripts.product import (
    GifProduct
)

from scripts.setup import (
    fund_riskpool,
    fund_customer,
)

from scripts.instance import GifInstance
from scripts.util import s2b32, contractFromAddress

# enforce function isolation for tests below
@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass


# underwrite the policy after the apply_for_policy has failed due to low riskpool balance
def test_risk_creation_happy_case(
    instance: GifInstance, 
    gifProduct: GifProduct,
    insurer,
):
    product = gifProduct.getContract()
    multiplier = product.getPercentageMultiplier()
    coordMultiplier = product.getCoordinatesMultiplier()
    precMultiplier = product.getPrecipitationMultiplier()

    startDate = time.time() + 100
    endDate = time.time() + 1000
    placeId = s2b32('10001.saopaulo') # mm 
    lat = -23.550620
    long = -46.634370
    trigger = 0.1 # %
    exit = 1.0 # %
    precHist = 5.0 # mm

    riskId = create_risk(product, insurer, startDate, endDate, placeId, lat, long, trigger, exit, precHist)
    risk = product.getRisk(riskId)

    assert risk[0] == riskId
    assert risk[1] == startDate
    assert risk[2] == endDate
    assert risk[3] == placeId
    assert risk[4] == coordMultiplier * lat
    assert risk[5] == coordMultiplier * long
    assert risk[6] == multiplier * trigger
    assert risk[7] == multiplier * exit
    assert risk[8] == precMultiplier * precHist

    # attempt to modify risk
    with brownie.reverts('ERROR:RAIN-001:RISK_ALREADY_EXISTS'):
        create_risk(product, insurer, startDate, endDate, placeId, lat, long, trigger, exit, precHist * 0.9)


def test_risk_creation_validation(
    instance: GifInstance, 
    gifProduct: GifProduct,
    insurer,
):
    product = gifProduct.getContract()
    
    startDate = time.time() + 100
    endDate = time.time() + 1000
    lat = -23.550620
    long = -46.634370
    trigger = 0.2 # %
    exit = 0.75 # %
    precHist = 5.0 # mm

    # check trigger validation: trigger <= 1.0
    valid_trigger = 0.2
    bad_trigger = 1.1

    create_risk(product, insurer, startDate, endDate, s2b32('1'), lat, long, valid_trigger, exit, precHist)

    with brownie.reverts('ERROR:RAIN-041:RISK_TRIGGER_TOO_LARGE'):
        create_risk(product, insurer, startDate, endDate, s2b32('2'), lat, long, bad_trigger, exit, precHist)

    # check trigger validation: trigger < exit
    bad_trigger1 = exit
    bad_trigger2 = exit + 0.1

    with brownie.reverts('ERROR:RAIN-042:RISK_EXIT_NOT_LARGER_THAN_TRIGGER'):
        create_risk(product, insurer, startDate, endDate, s2b32('3'), lat, long, bad_trigger1, exit, precHist)

    with brownie.reverts('ERROR:RAIN-042:RISK_EXIT_NOT_LARGER_THAN_TRIGGER'):
        create_risk(product, insurer, startDate, endDate, s2b32('4'), lat, long, bad_trigger2, exit, precHist)

    # check exit validation
    valid_exit = exit
    bad_exit1 = trigger - 0.1
    bad_exit2 = 0

    create_risk(product, insurer, startDate, endDate, s2b32('5'), lat, long, trigger, valid_exit, precHist)

    with brownie.reverts('ERROR:RAIN-042:RISK_EXIT_NOT_LARGER_THAN_TRIGGER'):
        create_risk(product, insurer, startDate, endDate, s2b32('6'), lat, long, trigger, bad_exit1, precHist)

    with brownie.reverts('ERROR:RAIN-042:RISK_EXIT_NOT_LARGER_THAN_TRIGGER'):
        create_risk(product, insurer, startDate, endDate, s2b32('7'), lat, long, trigger, bad_exit2, precHist)

    # check precHist validation
    # bad_aph = 0

    # with brownie.reverts('ERROR:RAIN-043:RISK_APH_ZERO_INVALID'):
    #     create_risk(product, insurer, startDate, endDate, s2b32('8'), lat, long, trigger, exit, bad_aph)

    # check dates validation
    bad_startDate1 = endDate + 500
    bad_startDate2 = time.time() - 500

    bad_endDate1 = time.time() - 500
    bad_endDate2 = startDate - 500

    create_risk(product, insurer, startDate, endDate, s2b32('9'), lat, long, trigger, exit, precHist)

    with brownie.reverts('ERROR:RAIN-045:RISK_END_DATE_INVALID'):
        create_risk(product, insurer, bad_startDate1, endDate, s2b32('10'), lat, long, trigger, exit, precHist)

    with brownie.reverts('ERROR:RAIN-044:RISK_START_DATE_INVALID'):
        create_risk(product, insurer, bad_startDate2, endDate, s2b32('11'), lat, long, trigger, exit, precHist)

    with brownie.reverts('ERROR:RAIN-045:RISK_END_DATE_INVALID'):
        create_risk(product, insurer, startDate, bad_endDate1, s2b32('12'), lat, long, trigger, exit, precHist)

    with brownie.reverts('ERROR:RAIN-045:RISK_END_DATE_INVALID'):
        create_risk(product, insurer, startDate, bad_endDate2, s2b32('13'), lat, long, trigger, exit, precHist)

def test_risk_adjustment_happy_case(
    instance: GifInstance, 
    gifProduct: GifProduct,
    insurer,
):
    product = gifProduct.getContract()
    multiplier = product.getPercentageMultiplier()
    coordMultiplier = product.getCoordinatesMultiplier()
    precMultiplier = product.getPrecipitationMultiplier()

    startDate = time.time() + 100
    endDate = time.time() + 1000
    placeId = s2b32('10001.saopaulo') # mm 
    lat = -23.550620
    long = -46.634370
    trigger = 0.1 # %
    exit = 1.0 # %
    precHist = 5.0 # mm

    riskId = create_risk(product, insurer, startDate, endDate, placeId, lat, long, trigger, exit, precHist)

    trigger_new = 0.2 * multiplier
    exit_new = 0.75 * multiplier
    aph_new = 2.0 * precMultiplier

    tx = product.adjustRisk(riskId, trigger_new, exit_new, aph_new, {'from': insurer})
    print(tx.info())

    risk = product.getRisk(riskId)
    assert risk[0] == riskId
    assert risk[1] == startDate
    assert risk[2] == endDate
    assert risk[3] == placeId
    assert risk[4] == coordMultiplier * lat
    assert risk[5] == coordMultiplier * long
    assert risk[6] == trigger_new
    assert risk[7] == exit_new
    assert risk[8] == aph_new

def test_risk_adjustment_with_policy(
    instance: GifInstance, 
    instanceOperator, 
    gifProduct: GifProduct,
    riskpoolWallet,
    riskpoolKeeper: Account,    
    investor,
    insurer,
    customer,
):
    instanceService = instance.getInstanceService()

    product = gifProduct.getContract()
    oracle = gifProduct.getOracle().getContract()
    riskpool = gifProduct.getRiskpool().getContract()

    token = gifProduct.getToken()
    riskpoolFunding = 200000
    fund_riskpool(
        instance, 
        instanceOperator, 
        riskpoolWallet, 
        riskpool, 
        investor, 
        token, 
        riskpoolFunding)

    customerFunding = 500
    fund_customer(instance, instanceOperator, customer, token, customerFunding)

    multiplier = product.getPercentageMultiplier()
    coordMultiplier = product.getCoordinatesMultiplier()
    precMultiplier = product.getPrecipitationMultiplier()

    startDate = time.time() + 100
    endDate = time.time() + 1000
    placeId = s2b32('10001.saopaulo') # mm 
    lat = -23.550620
    long = -46.634370
    trigger = 0.1 # %
    exit = 1.0 # %
    precHist = 2.0 # mm

    riskId = create_risk(product, insurer, startDate, endDate, placeId, lat, long, trigger, exit, precHist)

    premium = 300
    sumInsured = 2000
    tx = product.applyForPolicy(customer, premium, sumInsured, riskId, {'from': insurer})
    processId = tx.return_value

    assert product.policies(riskId) == 1
    assert product.getPolicyId(riskId, 0) == processId

    trigger_new = 0.2 * multiplier
    exit_new = 0.75 * multiplier
    aph_new = 3.0 * precMultiplier

    with brownie.reverts('ERROR:RAIN-003:RISK_WITH_POLICIES_NOT_ADJUSTABLE'):
        product.adjustRisk(riskId, trigger_new, exit_new, aph_new, {'from': insurer})


def create_risk(product, insurer, startDate, endDate, placeId, lat, long, trigger, exit, precHist):
    multiplier = product.getPercentageMultiplier()
    coordMultiplier = product.getCoordinatesMultiplier()
    precMultiplier = product.getPrecipitationMultiplier()
    tx = product.createRisk(
        startDate,
        endDate,
        placeId,
        lat * coordMultiplier,
        long * coordMultiplier,
        trigger * multiplier,
        exit * multiplier,
        precHist * precMultiplier,
        {'from': insurer }
    )

    return tx.return_value
