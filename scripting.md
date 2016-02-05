Fun With FreeNAS!
------
------

An Anonymous FreeNAS Dev (Do Not Git Blame this line): "The Only thing we changed in FreeNAS 10 is
Everything!"

Yo Dawg I heard you like FreeNAS 10! Did you check out the ALL NEW Freenas CLI? NO! Why not? I am
here to give you some reasons to do so. This is a guide/exploration/example set of all the new shiny
features in the Amazeballs FreeNAS 10 CLI, with an emphasis on scripting and automation.

So before we stash the cake in the oven we should pre-heat the oven, so starting off with variable
seems like a good idea before we delve straight into lamda functions and raising 'foo' to the nth
power of 'not bar'.

# Variables
So lets fire up a cli instance from the shell in FreeNAS10.

```
[root@freenas] ~# cli
 _________________________________________ 
/ Welcome to the FreeNAS CLI! Type 'help' \
\ to get started.                         /
 ----------------------------------------- 
        \   ^__^
         \  (**)\_______
            (__)\       )\/\
             U  ||----w |
                ||     ||


You may try the following URLs to access the web user interface:
          URLs (url)
http://fe80::20c:29ff:fe23:3173 
http://192.168.1.128
http://192.168.221.136
http://fe80::20c:29ff:fe23:3169 
http://169.254.16.1
http://169.254.169.254
unix::>
```

~~Yes I love cows~~ Oops, I am not supposed to say that.

So how does one declare a variable you ask? Pretty intuitive actually...
```
unix::>var="hello world"
unix::>mynum=100
unix::>
```

and yes, you can use semicolons!
`unix::>a=1;b=2;c=3`

However, you might observer that if you try to print the variables by directyly typing them at our
prompt, it errors out as follows:

```
unix::>var
Error: hello world not found
```

So how do I print this new variable that I created? Well there really are a bunch of
different ways to do so but here are the two most easy and intuitve ones:

```
unix::>print(var)
hello world 
unix::>echo ${mynum}
100
unix::>echo I am saying: ${var} a ${mynum} times
I am saying: hello world a 100 times
unix::>print(a, b, c)
1 2 3 
unix::>
```

"Wait this is getting interesting can I haz other data structures like lists and dicts?"

Yes!

```
unix::>a=[1, 2,  3]
unix::>print(a)
[1, 2, 3]
unix::>b={"this": "foo", "that": "bar"}
unix::>echo ${b}
that=bar  this=foo
unix::>print(b)
that=bar  this=foo

unix::>print(b["this"])
foo 
unix::>
```


"Cool, but hey can I get the input from the say, the user?"

Ofcourse, this would not be a scripting tutorial if you could not :-P

```
unix::>secret_pass=readline("Hey Joe Smith enter your password for me to steal: ");
Hey Joe Smith enter your password for me to steal: meh
unix::>echo How do i feel about this password: ${secret_pass}
How do i feel about this password: meh
unix::>
```


"OK I GET IT! The CLI has Variables, what next?"

The oven's hot now so lets get this cake started.

# Builtin Functions

__Basic Operators__

Below are some examples of using the basic builtin operators

```
unix::>a=2*3
unix::>print(a)
6 

unix::>b=5*4/2
unix::>echo ${b}
10

unix::>res=10==b
unix::>print(res)
true 

unix::>c=1!=0
unix::>print(c)
true 

unix::>logicres=true and c
unix::>print(logicres)
true

unix::>logicres=false and c
unix::>print(logicres)
false 

unix::>orres=1 or 0
unix::>print(orres)
1

unix::>notres=not logicres
unix::>echo ${notres}
true
```

Note: These basic operations will not work without an assignemnt operation. .e. the following fails:

```
unix::>2*3
Syntax error: LexToken(MUL,'*',1,1)
```

Also here is the full list of operators we support:
 `'+','-''*','/','==','!=','>','<','>=','<=','and','or','not'`

__How to use the inbuilt factorial function__

```
unix::>factorial(5)
120
```

