# uv 
```
curl -LsSf https://astral.sh/uv/install.sh | sh
```


# rpi-rgb-led-matrix のsettoappu 


1. rpi-rgb-led-matrixのpull
git submoduleで持ってくる
```
git submodule update --init --recursive
```

2. Makefileの編集

`lib/rpi-matrix/bindings/python/rgbmatrix/Makefile`を編集する

"cython3" を "cython"に書き換える
※ pipなどでインストールすると，cythonとして仮想環境のbinディレクトリに配置されますが、cython3**というエイリアス（別名）は作成されないため

3. ビルド
```
source .venv/bin/activate
cd lib/rpi-matrix/bindings/python
make build-python PYTHON=$(which python3)
```

4. ライブラリ追加
```
make install-python PYTHON=$(which python3)
```

5. Makefileをもとに戻す＾＾


