cd ..
python -m unittest discover -f -s ./tests -p "*_test.py"
cd tests
read -n 1 -s -r -p "Press any key to continue"