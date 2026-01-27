.PHONY: build up process strict clean-generated

build:
	docker compose build

up:
	docker compose up

process:
	docker compose run --rm -e CONFIG_PATH=$(CONFIG) -e ACTION=process etl

strict:
	docker compose run --rm -e CONFIG_PATH=$(CONFIG) -e ACTION=$(ACTION) -e STRICT=true etl

clean-generated:
	rm -rf data/processed/*
	rm -rf data/malformed/*
	rm -rf logs/*
