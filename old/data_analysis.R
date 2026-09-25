library("tidyverse")
library("caret")

data <- read_csv('data.csv')

cleaned <- data %>%
  select(ftp,label,zid,pos,position_in_cat,cp,time_gun,gap,category,
         height,weight,age,np,avg_power,avg_wkg,wkg_ftp,wftp,
         w5,w15,w30,w60, w120, w300, w1200, male)

remove_brackets <- function(xvar){
  str_remove_all(xvar,"\\[|\\]|\\'") %>%
    str_split_fixed(",",2) %>%
    .[,1] %>%
    as.numeric()
}

cleaned <- cleaned %>%
  mutate(height = remove_brackets(height),
         weight = remove_brackets(weight),
         np = remove_brackets(np),
         avg_power = remove_brackets(avg_power),
         avg_wkg = remove_brackets(avg_wkg),
         wkg_ftp = remove_brackets(wkg_ftp),
         wftp = remove_brackets(wftp),
         w5=remove_brackets(w5),
         w15=remove_brackets(w15),
         w30 = remove_brackets(w30),
         w60=remove_brackets(w60),
         w120=remove_brackets(w120),
         w300=remove_brackets(w300),
         w1200 = remove_brackets(w1200),
         sex = if_else(male == 1,"man","women")
         )

# Me quedo con los eventos con más de 5 participantes por categoria
groups <- cleaned %>%
  group_by(zid,category) %>%
  summarise(n = n()) %>%
  filter(n > 5) %>%
  mutate(id_cat = paste0(zid,category))

cleaned <- cleaned %>%
  mutate(id_cat = paste0(zid,category),
         bmi = weight/(height/100)^2) %>%
  filter(id_cat %in% groups$id_cat,
         height > 0,
         weight > 0) %>%
  select(-id_cat)

# General idea
# optimization function: min(time_gun) by route.
model <- lm(time_gun ~ ftp + bmi + w5 + w15+ w30 + w60 + w120 + w300 + w1200 - 1,
            cleaned)

summary(model)

cleaned %>%
  group_by(zid) %>%
  summarise(time = min(time_gun),
            time_avg = mean(time_gun),
            time_max = max(time_gun))

# Create a model by route/event
library(broom)
models <- cleaned %>% 
  na.omit() %>%
  group_by(zid, category) %>%
  nest() %>% 
  mutate(fit = map(data, ~ lm(time_gun ~ ftp + bmi + w30 + w1200, data = .)),
         results = map(fit, augment),
         glance = map(fit, broom::glance)
         )

models %>% 
  unnest(glance)

models %>% 
  unnest(results)

