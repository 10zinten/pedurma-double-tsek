if [ -f .env ]; then
	echo "evnironment already created !"
	source .env/bin/activate
else
	python3 -m venv .env
	source .env/bin/activate
	pip install -r requirements.txt
fi

start-nb
