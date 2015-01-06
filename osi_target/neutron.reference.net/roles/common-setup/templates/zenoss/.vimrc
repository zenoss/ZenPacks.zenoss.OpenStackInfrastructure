set paste
set directory=/tmp/
set wrap

" if &term=="xterm"
"    map! Op 0
"    map! Oq 1
"    map! Or 2
"    map! Os 3
"    map! Ot 4
"    map! Ou 5
"    map! Ov 6
"    map! Ow 7
"    map! Ox 8
"    map! Oy 9
"    map! On .
" endif

" nmap <silent> gw "_yiw:s/\(\%#\w\+\)\(\W\+\)\(\w\+\)/\3\2\1/<cr><c-o><c-l>"
set tabstop=8
set softtabstop=3
set smartindent
set autoindent
set spellfile=~/.vim/dict.add
set nojoinspaces
set noic


set shiftwidth=3
set et
set textwidth=79
map <F1> :set paste!<bar>set paste?<CR>
map <F5> :set hls!<bar>set hls?<CR>
map <f7> :set spell!<bar>set spell?<bar>syn spell toplevel<CR>
map <F8> :syn spell toplevel<CR>
map <F9> :%s/.*/\L&/g<CR>


if &t_Co > 2 || has("gui_running")
  syntax on
  set hlsearch
endif
set ruler               " show the cursor position all the time

if has("autocmd")
  augroup vimrcEx
  au!
    " For all text files set 'textwidth' to 78 characters.
    autocmd FileType text setlocal textwidth=80
    "
    " When editing a file, always jump to the last known cursor position.
    " Don't do it when the position is invalid or when inside an event handler
    " (happens when dropping a file on gvim).
    autocmd BufReadPost *
      \ if line("'\"") > 0 && line("'\"") <= line("$") |
      \   exe "normal g`\"" |
      \ endif

  augroup END
  au BufRead *.txt set formatoptions=tcq2
endif " has("autocmd")


augroup vimrc_autocmds
 " autocmd BufEnter * highlight OverLength ctermbg=lightgreen guibg=#775544
 " autocmd BufEnter * match OverLength /\%80v.*/
augroup END

colorscheme slate

" Resize Window Splits
map <silent> <A-h> <C-w><
map <silent> <A-j> <C-W>-
map <silent> <A-k> <C-W>+
map <silent> <A-l> <C-w>>

