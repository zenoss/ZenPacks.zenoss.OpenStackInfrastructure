# .bashrc

# User specific aliases and functions

if [ "$PS1" ]; then

   # Source global definitions
   if [ -f /etc/bashrc ]; then
           . /etc/bashrc
   fi

   function d()
   { 
      exec ls -l "$@" | less -EXsM 
   }
   function D()
   { 
      exec ls -la "$@" | less -EXsM 
   }
   function dt()
   {
      exec ls -lt "$@" | less -EXsM 
   }

   alias m="less -EMsX $@"

   # PS1='[\u@\h:\w]: '
   if [ "`id -un`" = "root" ]; then
      PS1='[\[\e[1;31m\]\u@\h:\w\[\e[0m\]]: ';
   else
      PS1='[\[\e[1;30m\]\u@\h:\w\[\e[0m\]]: ';
   fi

   EDITOR=vi
   export PATH EDITOR
   export LC_COLLATE=C

stty erase 
fi

