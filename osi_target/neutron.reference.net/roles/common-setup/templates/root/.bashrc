# .bashrc

# User specific aliases and functions

if [ "$PS1" ]; then

   unset GNOME_KEYRING_CONTROL

   # Source global definitions
   if [ -f /etc/bashrc ]; then
           . /etc/bashrc
   fi

   if [ -f /etc/bash_completion ]; then
           . /etc/bash_completion
   fi

   if [ -f ~/alias.bash ]; then
           . ~/alias.bash
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

   # PS1='[\u@\h:\w]: '
   if [ "`id -un`" = "root" ]; then
      PS1='[\[\e[1;31m\]\u@\h:\w\[\e[0m\]]: ';
   else
      PS1='[\[\e[1;34m\]\u@\h:\w\[\e[0m\]]: ';
   fi

   PATH=$PATH:/usr/local/bin:$HOME/bin

   EDITOR=vi
   export PATH EDITOR

stty erase '^?'
fi

