from django.shortcuts import render,HttpResponse,redirect
from django.contrib import auth
from blog.models import UserInfo,Blog,Category,Tag,Article,Article2Tag,ArticleUpDown,Comment
from django.db.models import Count,Avg,Max,F
from django.http import JsonResponse
from cnblog import settings
import json
import os


# Create your views here.
def register(request):

    return render(request,'register.html')


def login(request):
    user = request.POST.get('user')
    pwd = request.POST.get('pwd')
    user = auth.authenticate(username=user,password=pwd)
    if user:
        auth.login(request,user)
        return redirect('/index/')

    return render(request,'login-1.html')

def logout(request):
    auth.logout(request)
    return redirect('/index/')

def index(request):
    article_list = Article.objects.all()

    return render(request,'index.html',{'article_list':article_list})

def homesite(request,username,**kwargs):
    user = UserInfo.objects.filter(username=username).first()
    if not user:
        return render(request,'not_found.html')
    blog = user.blog
    category_list = Category.objects.filter(blog=blog).values('pk').annotate(c=Count('article__title')).values_list('title','c')
    tag_list = Tag.objects.filter(blog=blog).values('pk').annotate(c=Count('article__nid')).values_list('title','c')
    date_list = Article.objects.filter(user=user).extra(select={'Y-m-date':"strftime('%%Y/%%m',create_time)"}).values('Y-m-date').annotate(c=Count('title')).values_list('Y-m-date','c')

    if not kwargs:
        article_list = Article.objects.filter(user__username=username)
    else:
        condition = kwargs.get('condition')
        params = kwargs.get('params')

        if condition == 'category':
            article_list = Article.objects.filter(user__username=username).filter(category__title=params)
        elif condition == 'tag':
            article_list = Article.objects.filter(user__username=username).filter(tag__title=params)
        else:
            year,month = params.split('/')
            article_list = Article.objects.filter(user__username=username).filter(create_time__year=year,create_time__month=month)

    if not article_list:
        return render(request, 'not_found.html')
    return render(request,'homesite.html',{'blog':blog,'article_list':article_list,'category_list':category_list,'tag_list':tag_list,'date_list':date_list,'username':username})


def article_detail(request,username,article_id):
    user = UserInfo.objects.filter(username=username).first()
    blog = user.blog
    category_list = Category.objects.filter(blog=blog).values('pk').annotate(c=Count('article__title')).values_list('title', 'c')
    tag_list = Tag.objects.filter(blog=blog).values('pk').annotate(c=Count('article__nid')).values_list('title', 'c')
    date_list = Article.objects.filter(user=user).extra(select={'Y-m-date': "strftime('%%Y/%%m',create_time)"}).values('Y-m-date').annotate(c=Count('title')).values_list('Y-m-date', 'c')

    article = Article.objects.filter(nid=article_id).first()
    comment_list = Comment.objects.filter(article_id=article_id)

    return render(request,'article_detail.html',{'user':user,'category_list':category_list,'tag_list':tag_list,'date_list':date_list,'article':article,'blog':blog,'username':username,'comment_list':comment_list})

from django.db import transaction
def digg(request):
    user_id = request.user.pk
    article_id = request.POST.get('article_id')
    is_up = json.loads(request.POST.get('is_up'))
    response = {'state':True,'msg':None}

    articleupdown_obj = ArticleUpDown.objects.filter(user_id=user_id,article_id=article_id).first()

    if articleupdown_obj:
        response['state']=False
        response['handles']=articleupdown_obj.is_up
    else:
        # 事务管理，执行上下文内容时遇到错误执行回滚操作，类似于mysql的事务回滚rollback
        with transaction.atomic():
            new_articleupdown_obj = ArticleUpDown.objects.create(user_id=user_id,article_id=article_id, is_up=is_up)
            if is_up:
                Article.objects.filter(pk=article_id).update(up_count=F('up_count')+1)
            else:
                Article.objects.filter(pk=article_id).update(down_count=F('down_count')+1)

    return JsonResponse(response)

def comment(request):
    user_id = request.user.pk
    article_id = request.POST.get('article_id')
    content = request.POST.get('content')
    parent_comment_id = request.POST.get('parent_comment_id')
    with transaction.atomic():
        comment = Comment.objects.create(user_id=user_id,article_id=article_id,content=content,parent_comment_id=parent_comment_id)
        Article.objects.filter(pk=article_id).update(comment_count =F('comment_count')+1 )

    response = {'state':True}
    response['create_time'] = comment.create_time.strftime('%Y-%m-%d %X')
    response['content'] = comment.content
    response['user']=request.user.username


    return JsonResponse(response)

def backend(request):
    user = request.user
    article_list = Article.objects.filter(user=user)

    return render(request,'backend/backend.html',locals())

def add_article(request):
    if request.method == 'POST':
        title = request.POST.get('title')
        content = request.POST.get('content')
        user = request.user
        category_pk = request.POST.get('category')
        tag_pk_list = request.POST.getlist('tag')

        from bs4 import BeautifulSoup #解析模块
        soup = BeautifulSoup(content,'html.parser') #实例化一个soup对象，解析器html.parser
        # 防御xss攻击
        for tag in soup.find_all():
            if tag.name =='script':
                tag.decompose()
        desc=soup.text[1:150]

        article_obj = Article.objects.create(title=title,content=str(soup),user=user,category_id=category_pk,desc=desc)
        for tag_pk in tag_pk_list:
            Article2Tag.objects.create(article_id=article_obj.pk,tag_id=tag_pk)
        return redirect('/backend/')


    else:
        blog = request.user.blog
        category_list = Category.objects.filter(blog=blog)
        tag_list = Tag.objects.filter(blog=blog)

        return render(request,'backend/add_article.html',{'category_list':category_list,'tag_list':tag_list})

def upload(request):
    upload_obj = request.FILES.get('upload_img')
    name=upload_obj.name
    # print(name) #上传img文件的名字
    path=os.path.join(settings.BASE_DIR,'static','upload',name)
    with open(path,'wb') as f:
        for obj in upload_obj:
            f.write(obj)
    res = {
        'error':0,
        'url':'/static/upload/'+name
    }

    return HttpResponse(json.dumps(res))

def del_article(request,id):

    response = {'state':True}
    try:
        Article2Tag.objects.filter(tag_id=id).delete()
        Article.objects.filter(nid=id).delete()

    except Exception as e:
        response['state']=False

    return HttpResponse(json.dumps(response))