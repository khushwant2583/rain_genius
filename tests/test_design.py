import pytest
from agent.design import calculate_harvestable_water

def test_known_calculation():
    r=calculate_harvestable_water(500,120,0.8,1.0)
    assert r["theoretical_runoff_l"] == 48000 and r["estimated_collectable_l"] == 48000

def test_efficiency_applied(): assert calculate_harvestable_water(500,120,0.8,0.9)["estimated_collectable_l"] == 43200

def test_negative_rainfall_rejected():
    with pytest.raises(ValueError): calculate_harvestable_water(-1,120,.8)

def test_bad_coefficient_rejected():
    with pytest.raises(ValueError): calculate_harvestable_water(500,120,1.2)
