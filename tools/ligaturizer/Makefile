default: ligaturize

ligaturize:
	python ligaturize.py src-fonts/source-code-pro/source-code-pro-regular.ttf \
		--ligature-font-file='./src-fonts/fira-code/FiraCode-Regular.ttf' \
		--output-dir='output/' \
		--prefix='liga' \
		--output-name='source-code-pro-regular' \
		2>&1 \
	| grep -Fv 'This contextual rule applies no lookups.' \
	| grep -Fv 'Bad device table'

